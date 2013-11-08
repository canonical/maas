# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test DNS module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from functools import partial
from itertools import islice
import socket

from celery.task import task
from django.conf import settings
from django.core.management import call_command
from maasserver import (
    dns,
    server_address,
    )
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Config,
    node as node_module,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.bindfixture import BINDServer
from maastesting.celery import CeleryFixture
from maastesting.fakemethod import FakeMethod
from maastesting.tests.test_bindfixture import dig_call
from mock import (
    ANY,
    call,
    Mock,
    )
from netaddr import (
    IPNetwork,
    IPRange,
    )
from provisioningserver import tasks
from provisioningserver.dns.config import (
    conf,
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    DNSZoneConfigBase,
    )
from provisioningserver.dns.utils import generated_hostname
from rabbitfixture.server import allocate_ports
from testresources import FixtureResource
from testtools.matchers import (
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesStructure,
    )


class TestDNSUtilities(MAASServerTestCase):

    def test_zone_serial_parameters(self):
        self.assertThat(
            dns.zone_serial,
            MatchesStructure.byEquality(
                maxvalue=2 ** 32 - 1,
                minvalue=1,
                incr=1,
                )
            )

    def test_next_zone_serial_returns_sequence(self):
        initial = int(dns.next_zone_serial())
        self.assertSequenceEqual(
            ['%0.10d' % i for i in range(initial + 1, initial + 11)],
            [dns.next_zone_serial() for i in range(initial, initial + 10)])

    def patch_DEFAULT_MAAS_URL_with_random_values(self, hostname=None):
        if hostname is None:
            hostname = factory.getRandomString()
        url = 'http://%s:%d/%s' % (
            hostname, factory.getRandomPort(), factory.getRandomString())
        self.patch(settings, 'DEFAULT_MAAS_URL', url)

    def test_get_dns_server_address_resolves_hostname(self):
        ip = factory.getRandomIPAddress()
        resolver = FakeMethod(result=ip)
        self.patch(server_address, 'gethostbyname', resolver)
        hostname = factory.make_hostname()
        self.patch_DEFAULT_MAAS_URL_with_random_values(hostname=hostname)
        self.assertEqual(
            (ip, [(hostname, )]),
            (dns.get_dns_server_address(), resolver.extract_args()))

    def test_get_dns_server_address_raises_if_hostname_doesnt_resolve(self):
        self.patch(
            dns, 'get_maas_facing_server_address',
            FakeMethod(failure=socket.error))
        self.patch_DEFAULT_MAAS_URL_with_random_values()
        self.assertRaises(dns.DNSException, dns.get_dns_server_address)

    def test_get_dns_server_address_logs_warning_if_ip_is_localhost(self):
        logger = self.patch(dns, 'logger')
        self.patch(
            dns, 'get_maas_facing_server_address',
            Mock(return_value='127.0.0.1'))
        dns.get_dns_server_address()
        self.assertEqual(
            call(dns.WARNING_MESSAGE % '127.0.0.1'),
            logger.warn.call_args)

    def test_get_dns_server_address_uses_nodegroup_maas_url(self):
        ip = factory.getRandomIPAddress()
        resolver = FakeMethod(result=ip)
        self.patch(server_address, 'gethostbyname', resolver)
        hostname = factory.make_hostname()
        maas_url = 'http://%s' % hostname
        nodegroup = factory.make_node_group(maas_url=maas_url)
        self.assertEqual(
            (ip, [(hostname, )]),
            (dns.get_dns_server_address(nodegroup), resolver.extract_args()))

    def test_is_dns_managed(self):
        nodegroups_with_expected_results = {
            factory.make_node_group(
                status=NODEGROUP_STATUS.PENDING,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS): False,
            factory.make_node_group(
                status=NODEGROUP_STATUS.REJECTED,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS): False,
            factory.make_node_group(
                status=NODEGROUP_STATUS.ACCEPTED,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS): True,
            factory.make_node_group(
                status=NODEGROUP_STATUS.ACCEPTED,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP): False,
            factory.make_node_group(
                status=NODEGROUP_STATUS.ACCEPTED,
                management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED): False,
        }
        results = {
            nodegroup: dns.is_dns_managed(nodegroup)
            for nodegroup, _ in nodegroups_with_expected_results.items()
        }
        self.assertEqual(nodegroups_with_expected_results, results)


class TestDNSConfigModifications(MAASServerTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def setUp(self):
        super(TestDNSConfigModifications, self).setUp()
        self.bind = self.useFixture(BINDServer())
        self.patch(conf, 'DNS_CONFIG_DIR', self.bind.config.homedir)

        # Use a random port for rndc.
        self.patch(conf, 'DNS_RNDC_PORT', allocate_ports("localhost")[0])
        # This simulates what should happen when the package is
        # installed:
        # Create MAAS-specific DNS configuration files.
        call_command('set_up_dns')
        # Register MAAS-specific DNS configuration files with the
        # system's BIND instance.
        call_command(
            'get_named_conf', edit=True,
            config_path=self.bind.config.conf_file)
        # Reload BIND.
        self.bind.runner.rndc('reload')

    def create_managed_nodegroup(self):
        return factory.make_node_group(
            network=IPNetwork('192.168.0.1/24'),
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)

    def create_nodegroup_with_lease(self, lease_number=1, nodegroup=None):
        if nodegroup is None:
            nodegroup = self.create_managed_nodegroup()
        interface = nodegroup.get_managed_interface()
        node = factory.make_node(
            nodegroup=nodegroup)
        mac = factory.make_mac_address(node=node)
        ips = IPRange(interface.ip_range_low, interface.ip_range_high)
        lease_ip = unicode(islice(ips, lease_number, lease_number + 1).next())
        lease = factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=mac.mac_address, ip=lease_ip)
        # Simulate that this lease was created by
        # DHCPLease.objects.update_leases: update its DNS config.
        dns.change_dns_zones([nodegroup])
        return nodegroup, node, lease

    def dig_resolve(self, fqdn):
        """Resolve `fqdn` using dig.  Returns a list of results."""
        return dig_call(
            port=self.bind.config.port,
            commands=[fqdn, '+short']).split('\n')

    def dig_reverse_resolve(self, ip):
        """Reverse resolve `ip` using dig.  Returns a list of results."""
        return dig_call(
            port=self.bind.config.port,
            commands=['-x', ip, '+short']).split('\n')

    def assertDNSMatches(self, hostname, domain, ip):
        fqdn = "%s.%s" % (hostname, domain)
        autogenerated_hostname = '%s.' % generated_hostname(ip, domain)
        forward_lookup_result = self.dig_resolve(fqdn)
        if '%s.' % fqdn == autogenerated_hostname:
            # If the fqdn is an autogenerated hostname, it resolves to the IP
            # address (A record).
            expected_results = [ip]
        else:
            # If the fqdn is a custom hostname, it resolves to the
            # autogenerated hostname (CNAME record) and the IP address
            # (A record).
            expected_results = [autogenerated_hostname, ip]
        self.assertEqual(
            expected_results, forward_lookup_result,
            "Failed to resolve '%s' (results: '%s')." % (
                fqdn, ','.join(forward_lookup_result)))
        # A reverse lookup on the IP returns the autogenerated
        # hostname.
        reverse_lookup_result = self.dig_reverse_resolve(ip)
        self.assertEqual(
            [autogenerated_hostname], reverse_lookup_result,
            "Failed to reverse resolve '%s' (results: '%s')." % (
                fqdn, ','.join(reverse_lookup_result)))

    def test_add_zone_loads_dns_zone(self):
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        self.patch(settings, 'DNS_CONNECT', True)
        dns.add_zone(nodegroup)
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_change_dns_zone_changes_dns_zone(self):
        nodegroup, _, _ = self.create_nodegroup_with_lease()
        self.patch(settings, 'DNS_CONNECT', True)
        dns.write_full_dns_config()
        nodegroup, new_node, new_lease = (
            self.create_nodegroup_with_lease(
                nodegroup=nodegroup, lease_number=2))
        dns.change_dns_zones(nodegroup)
        self.assertDNSMatches(new_node.hostname, nodegroup.name, new_lease.ip)

    def test_is_dns_enabled_return_false_if_DNS_CONNECT_False(self):
        self.patch(settings, 'DNS_CONNECT', False)
        self.assertFalse(dns.is_dns_enabled())

    def test_is_dns_enabled_return_True_if_DNS_CONNECT_True(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.assertTrue(dns.is_dns_enabled())

    def test_is_dns_in_use_return_False_no_configured_interface(self):
        self.assertFalse(dns.is_dns_in_use())

    def test_is_dns_in_use_return_True_if_configured_interface(self):
        self.create_managed_nodegroup()
        self.assertTrue(dns.is_dns_in_use())

    def test_write_full_dns_loads_full_dns_config(self):
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        self.patch(settings, 'DNS_CONNECT', True)
        dns.write_full_dns_config()
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_write_full_dns_passes_reload_retry_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        recorder = FakeMethod()
        self.create_managed_nodegroup()

        @task
        def recorder_task(*args, **kwargs):
            return recorder(*args, **kwargs)
        self.patch(tasks, 'rndc_command', recorder_task)
        dns.write_full_dns_config(reload_retry=True)
        self.assertEqual(
            ([(['reload'], True)]), recorder.extract_args())

    def test_write_full_dns_passes_upstream_dns_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.create_managed_nodegroup()
        random_ip = factory.getRandomIPAddress()
        Config.objects.set_config("upstream_dns", random_ip)
        patched_task = self.patch(dns.tasks.write_full_dns_config, "delay")
        dns.write_full_dns_config()
        patched_task.assert_called_once_with(
            zones=ANY, callback=ANY, upstream_dns=random_ip)

    def test_write_full_dns_doesnt_call_task_it_no_interface_configured(self):
        self.patch(settings, 'DNS_CONNECT', True)
        patched_task = self.patch(dns.tasks.write_full_dns_config, "delay")
        dns.write_full_dns_config()
        self.assertEqual(0, patched_task.call_count)

    def test_dns_config_has_NS_record(self):
        ip = factory.getRandomIPAddress()
        self.patch(settings, 'DEFAULT_MAAS_URL', 'http://%s/' % ip)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        self.patch(settings, 'DNS_CONNECT', True)
        dns.write_full_dns_config()
        # Get the NS record for the zone 'nodegroup.name'.
        ns_record = dig_call(
            port=self.bind.config.port,
            commands=[nodegroup.name, 'NS', '+short'])
        # Resolve that hostname.
        ip_of_ns_record = dig_call(
            port=self.bind.config.port, commands=[ns_record, '+short'])
        self.assertEqual(ip, ip_of_ns_record)

    def test_add_nodegroup_creates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.getRandomIPInNetwork(network)
        nodegroup = factory.make_node_group(
            network=network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        self.assertDNSMatches(generated_hostname(ip), nodegroup.name, ip)

    def test_edit_nodegroupinterface_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        old_network = IPNetwork('192.168.7.1/24')
        old_ip = factory.getRandomIPInNetwork(old_network)
        nodegroup = factory.make_node_group(
            network=old_network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        interface = nodegroup.get_managed_interface()
        # Edit nodegroup's network information to '192.168.44.1/24'
        interface.ip = '192.168.44.7'
        interface.router_ip = '192.168.44.14'
        interface.broadcast_ip = '192.168.44.255'
        interface.netmask = '255.255.255.0'
        interface.ip_range_low = '192.168.44.0'
        interface.ip_range_high = '192.168.44.255'
        interface.save()
        ip = factory.getRandomIPInNetwork(IPNetwork('192.168.44.1/24'))
        # The ip from the old network does not resolve anymore.
        self.assertEqual([''], self.dig_resolve(generated_hostname(old_ip)))
        self.assertEqual([''], self.dig_reverse_resolve(old_ip))
        # The ip from the new network resolves.
        self.assertDNSMatches(generated_hostname(ip), nodegroup.name, ip)

    def test_changing_interface_management_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.getRandomIPInNetwork(network)
        nodegroup = factory.make_node_group(
            network=network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        interface = nodegroup.get_managed_interface()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.assertEqual([''], self.dig_resolve(generated_hostname(ip)))
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_delete_nodegroup_disables_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.getRandomIPInNetwork(network)
        nodegroup = factory.make_node_group(
            network=network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        nodegroup.delete()
        self.assertEqual([''], self.dig_resolve(generated_hostname(ip)))
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_add_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_delete_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        # Prevent omshell task dispatch.
        self.patch(node_module, "remove_dhcp_host_map")
        node.delete()
        fqdn = "%s.%s" % (node.hostname, nodegroup.name)
        self.assertEqual([''], self.dig_resolve(fqdn))

    def test_change_node_hostname_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        node.hostname = factory.make_name('hostname')
        node.save()
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_change_node_other_field_does_not_update_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        recorder = FakeMethod()
        self.patch(DNSZoneConfigBase, 'write_config', recorder)
        node.error = factory.getRandomString()
        node.save()
        self.assertEqual(0, recorder.call_count)


def forward_zone(domain, *networks):
    """
    Returns a matcher for a :class:`DNSForwardZoneConfig` with the given
    domain and networks.
    """
    networks = {IPNetwork(network) for network in networks}
    return MatchesAll(
        IsInstance(DNSForwardZoneConfig),
        MatchesStructure.byEquality(
            domain=domain, networks=networks))


def reverse_zone(domain, network):
    """
    Returns a matcher for a :class:`DNSReverseZoneConfig` with the given
    domain and network.
    """
    network = network if network is None else IPNetwork(network)
    return MatchesAll(
        IsInstance(DNSReverseZoneConfig),
        MatchesStructure.byEquality(
            domain=domain, network=network))


class TestZoneGenerator(MAASServerTestCase):
    """Tests for :class:x`dns.ZoneGenerator`."""

    # Factory to return an accepted nodegroup with a managed interface.
    make_node_group = partial(
        factory.make_node_group, status=NODEGROUP_STATUS.ACCEPTED,
        management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)

    def test_with_no_nodegroups_yields_nothing(self):
        self.assertEqual([], dns.ZoneGenerator(()).as_list())

    def test_with_one_nodegroup_yields_forward_and_reverse_zone(self):
        nodegroup = self.make_node_group(
            name="henry", network=IPNetwork("10/32"))
        zones = dns.ZoneGenerator(nodegroup).as_list()
        self.assertThat(
            zones, MatchesListwise(
                (forward_zone("henry", "10/32"),
                 reverse_zone("henry", "10/32"))))

    def test_with_many_nodegroups_yields_many_zones(self):
        # This demonstrates ZoneGenerator in all-singing all-dancing mode.
        nodegroups = [
            self.make_node_group(name="one", network=IPNetwork("10/32")),
            self.make_node_group(name="one", network=IPNetwork("11/32")),
            self.make_node_group(name="two", network=IPNetwork("20/32")),
            self.make_node_group(name="two", network=IPNetwork("21/32")),
            ]
        [  # Other nodegroups.
            self.make_node_group(name="one", network=IPNetwork("12/32")),
            self.make_node_group(name="two", network=IPNetwork("22/32")),
            ]
        expected_zones = (
            # For the forward zones, all nodegroups sharing a domain name,
            # even those not passed into ZoneGenerator, are consolidated into
            # a single forward zone description.
            forward_zone("one", "10/32", "11/32", "12/32"),
            forward_zone("two", "20/32", "21/32", "22/32"),
            # For the reverse zones, a single reverse zone description is
            # generated for each nodegroup passed in, in network order.
            reverse_zone("one", "10/32"),
            reverse_zone("one", "11/32"),
            reverse_zone("two", "20/32"),
            reverse_zone("two", "21/32"),
            )
        self.assertThat(
            dns.ZoneGenerator(nodegroups).as_list(),
            MatchesListwise(expected_zones))
