# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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


from itertools import islice
import random

from celery.task import task
from django.conf import settings
from django.core.management import call_command
from maasserver.dns import config as dns_config_module
from maasserver.dns.config import (
    add_zone,
    change_dns_zones,
    get_trusted_networks,
    is_dns_enabled,
    is_dns_in_use,
    next_zone_serial,
    tasks as dns_tasks,
    write_full_dns_config,
    zone_serial,
    )
from maasserver.enum import (
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Config,
    node as node_module,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import MockCalledOnceWith
from mock import ANY
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
    )
from provisioningserver import tasks
from provisioningserver.dns.config import (
    compose_config_path,
    DNSConfig,
    )
from provisioningserver.dns.testing import (
    patch_dns_config_path,
    patch_dns_rndc_port,
    )
from provisioningserver.dns.zoneconfig import DNSZoneConfigBase
from provisioningserver.testing.bindfixture import BINDServer
from provisioningserver.testing.tests.test_bindfixture import dig_call
from rabbitfixture.server import allocate_ports
from testtools.matchers import (
    Contains,
    FileContains,
    MatchesStructure,
    )


class TestDNSUtilities(MAASServerTestCase):

    def test_zone_serial_parameters(self):
        self.assertThat(
            zone_serial,
            MatchesStructure.byEquality(
                maxvalue=2 ** 32 - 1,
                minvalue=1,
                incr=1,
                )
            )

    def test_next_zone_serial_returns_sequence(self):
        initial = int(next_zone_serial())
        self.assertSequenceEqual(
            ['%0.10d' % i for i in range(initial + 1, initial + 11)],
            [next_zone_serial() for _ in range(initial, initial + 10)])


class TestDNSServer(MAASServerTestCase):
    """A base class to perform real-world DNS-related tests.

    The class starts a BINDServer for every test and provides a set of
    helper methods to perform DNS queries.

    Because of the overhead added by starting and stopping the DNS
    server, new tests in this class and its descendants are expensive.
    """

    def setUp(self):
        super(TestDNSServer, self).setUp()
        self.bind = self.useFixture(BINDServer())
        patch_dns_config_path(self, self.bind.config.homedir)
        # Use a random port for rndc.
        patch_dns_rndc_port(self, allocate_ports("localhost")[0])
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

    def create_managed_nodegroup(self, network=None):
        if network is None:
            network = IPNetwork('192.168.0.1/24')
        return factory.make_NodeGroup(
            network=network,
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)

    def create_nodegroup_with_static_ip(self, lease_number=1, nodegroup=None):
        if nodegroup is None:
            nodegroup = self.create_managed_nodegroup()
        [interface] = nodegroup.get_managed_interfaces()
        node = factory.make_Node(nodegroup=nodegroup, disable_ipv4=False)
        mac = factory.make_MACAddress(node=node, cluster_interface=interface)
        ips = IPRange(
            interface.static_ip_range_low, interface.static_ip_range_high)
        static_ip = unicode(islice(ips, lease_number, lease_number + 1).next())
        staticaddress = factory.make_StaticIPAddress(ip=static_ip, mac=mac)
        change_dns_zones([nodegroup])
        return nodegroup, node, staticaddress

    def dig_resolve(self, fqdn, version=4):
        """Resolve `fqdn` using dig.  Returns a list of results."""
        # Using version=6 has two effects:
        # - it changes the type of query from 'A' to 'AAAA';
        # - it forces dig to only use IPv6 query transport.
        record_type = 'AAAA' if version == 6 else 'A'
        commands = [fqdn, '+short', '-%i' % version, record_type]
        return dig_call(
            port=self.bind.config.port,
            commands=commands).split('\n')

    def dig_reverse_resolve(self, ip, version=4):
        """Reverse resolve `ip` using dig.  Returns a list of results."""
        return dig_call(
            port=self.bind.config.port,
            commands=['-x', ip, '+short', '-%i' % version]).split('\n')

    def assertDNSMatches(self, hostname, domain, ip, version=4):
        # A forward lookup on the hostname returns the IP address.
        fqdn = "%s.%s" % (hostname, domain)
        forward_lookup_result = self.dig_resolve(fqdn, version=version)
        self.assertEqual(
            [ip], forward_lookup_result,
            "Failed to resolve '%s' (results: '%s')." % (
                fqdn, ','.join(forward_lookup_result)))
        # A reverse lookup on the IP address returns the hostname.
        reverse_lookup_result = self.dig_reverse_resolve(
            ip, version=version)
        self.assertEqual(
            ["%s." % fqdn], reverse_lookup_result,
            "Failed to reverse resolve '%s' (results: '%s')." % (
                fqdn, ','.join(reverse_lookup_result)))


class TestDNSConfigModifications(TestDNSServer):

    def test_add_zone_loads_dns_zone(self):
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        add_zone(nodegroup)
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_add_zone_preserves_trusted_networks(self):
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, 'get_trusted_networks')
        get_trusted_networks_patch.return_value = trusted_network + ';'
        self.patch(settings, 'DNS_CONNECT', True)
        add_zone(nodegroup)
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)))

    def test_change_dns_zone_changes_dns_zone(self):
        nodegroup, _, _ = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        write_full_dns_config()
        nodegroup, new_node, new_static = (
            self.create_nodegroup_with_static_ip(
                nodegroup=nodegroup, lease_number=2))
        change_dns_zones(nodegroup)
        self.assertDNSMatches(new_node.hostname, nodegroup.name, new_static.ip)

    def test_is_dns_enabled_return_false_if_DNS_CONNECT_False(self):
        self.patch(settings, 'DNS_CONNECT', False)
        self.assertFalse(is_dns_enabled())

    def test_is_dns_enabled_return_True_if_DNS_CONNECT_True(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.assertTrue(is_dns_enabled())

    def test_is_dns_in_use_return_False_no_configured_interface(self):
        self.assertFalse(is_dns_in_use())

    def test_is_dns_in_use_return_True_if_configured_interface(self):
        self.create_managed_nodegroup()
        self.assertTrue(is_dns_in_use())

    def test_write_full_dns_loads_full_dns_config(self):
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        write_full_dns_config()
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_write_full_dns_passes_reload_retry_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        recorder = FakeMethod()
        self.create_managed_nodegroup()

        @task
        def recorder_task(*args, **kwargs):
            return recorder(*args, **kwargs)
        self.patch(tasks, 'rndc_command', recorder_task)
        write_full_dns_config(reload_retry=True)
        self.assertEqual(
            ([(['reload'], True)]), recorder.extract_args())

    def test_write_full_dns_passes_upstream_dns_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.create_managed_nodegroup()
        random_ip = factory.make_ipv4_address()
        Config.objects.set_config("upstream_dns", random_ip)
        patched_task = self.patch(dns_tasks.write_full_dns_config, "delay")
        write_full_dns_config()
        self.assertThat(patched_task, MockCalledOnceWith(
            zones=ANY, callback=ANY, trusted_networks=ANY,
            upstream_dns=random_ip))

    def test_write_full_dns_writes_trusted_networks_parameter(self):
        self.patch(settings, 'DNS_CONNECT', True)
        self.create_managed_nodegroup()
        trusted_network = factory.make_ipv4_address()
        get_trusted_networks_patch = self.patch(
            dns_config_module, 'get_trusted_networks')
        get_trusted_networks_patch.return_value = trusted_network + ';'
        write_full_dns_config()
        self.assertThat(
            compose_config_path(DNSConfig.target_file_name),
            FileContains(matcher=Contains(trusted_network)))

    def test_write_full_dns_doesnt_call_task_it_no_interface_configured(self):
        self.patch(settings, 'DNS_CONNECT', True)
        patched_task = self.patch(dns_tasks.write_full_dns_config, "delay")
        write_full_dns_config()
        self.assertEqual(0, patched_task.call_count)

    def test_dns_config_has_NS_record(self):
        ip = factory.make_ipv4_address()
        self.patch(settings, 'DEFAULT_MAAS_URL', 'http://%s/' % ip)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.patch(settings, 'DNS_CONNECT', True)
        write_full_dns_config()
        # Get the NS record for the zone 'nodegroup.name'.
        ns_record = dig_call(
            port=self.bind.config.port,
            commands=[nodegroup.name, 'NS', '+short'])
        # Resolve that hostname.
        ip_of_ns_record = dig_call(
            port=self.bind.config.port, commands=[ns_record, '+short'])
        self.assertEqual(ip, ip_of_ns_record)

    def test_edit_nodegroupinterface_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        old_network = IPNetwork('192.168.7.1/24')
        nodegroup = factory.make_NodeGroup(
            network=old_network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        _, node, lease = self.create_nodegroup_with_static_ip(
            nodegroup=nodegroup)
        self.assertEqual(
            ["%s." % node.fqdn], self.dig_reverse_resolve(lease.ip))
        # Edit nodegroup's network information to '192.168.44.1/24'
        interface.ip = '192.168.44.7'
        interface.router_ip = '192.168.44.14'
        interface.broadcast_ip = '192.168.44.255'
        interface.netmask = '255.255.255.0'
        interface.ip_range_low = '192.168.44.0'
        interface.ip_range_high = '192.168.44.128'
        interface.static_ip_range_low = '192.168.44.129'
        interface.static_ip_range_high = '192.168.44.255'
        interface.save()
        # The IP from the old network does not resolve anymore.
        self.assertEqual([''], self.dig_reverse_resolve(lease.ip))
        # A lease in the new network resolves.
        _, node, lease = self.create_nodegroup_with_static_ip(
            nodegroup=nodegroup)
        self.assertTrue(
            IPAddress(lease.ip) in interface.network,
            "The lease IP Address is not in the new network")
        self.assertEqual(
            ["%s." % node.fqdn], self.dig_reverse_resolve(lease.ip))

    def test_changing_interface_management_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.pick_ip_in_network(network)
        nodegroup = factory.make_NodeGroup(
            network=network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface] = nodegroup.get_managed_interfaces()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_delete_nodegroup_disables_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.pick_ip_in_network(network)
        nodegroup = factory.make_NodeGroup(
            network=network, status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        nodegroup.delete()
        self.assertEqual([''], self.dig_reverse_resolve(ip))

    def test_add_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_delete_node_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        self.patch_autospec(node_module, "remove_host_maps")
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        node.delete()
        fqdn = "%s.%s" % (node.hostname, nodegroup.name)
        self.assertEqual([''], self.dig_resolve(fqdn))

    def test_change_node_hostname_updates_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        node.hostname = factory.make_name('hostname')
        node.save()
        self.assertDNSMatches(node.hostname, nodegroup.name, static.ip)

    def test_change_node_other_field_does_not_update_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, static = self.create_nodegroup_with_static_ip()
        recorder = FakeMethod()
        self.patch(DNSZoneConfigBase, 'write_config', recorder)
        node.error = factory.make_string()
        node.save()
        self.assertEqual(0, recorder.call_count)


class TestDNSBackwardCompat(TestDNSServer):
    """Allocated nodes with IP addresses in the dynamic range get a DNS
    record.
    """

    def test_bind_configuration_includes_dynamic_ips_of_deployed_nodes(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        nodegroup = self.create_managed_nodegroup(network=network)
        [interface] = nodegroup.get_managed_interfaces()
        node = factory.make_Node(
            nodegroup=nodegroup, status=NODE_STATUS.DEPLOYED,
            disable_ipv4=False)
        mac = factory.make_MACAddress(node=node, cluster_interface=interface)
        # Get an IP in the dynamic range.
        ip_range = IPRange(
            interface.ip_range_low, interface.ip_range_high)
        ip = "%s" % random.choice(ip_range)
        lease = factory.make_DHCPLease(
            nodegroup=nodegroup, mac=mac.mac_address, ip=ip)
        change_dns_zones([nodegroup])
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)


class TestIPv6DNS(TestDNSServer):

    def test_bind_configuration_includes_ipv6_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('fe80::/64')
        nodegroup = self.create_managed_nodegroup(network=network)
        nodegroup, node, static = self.create_nodegroup_with_static_ip(
            nodegroup=nodegroup)
        self.assertDNSMatches(
            node.hostname, nodegroup.name, static.ip, version=6)


class TestGetTrustedNetworks(MAASServerTestCase):
    """Test for maasserver/dns/config.py:get_trusted_networks()"""

    def test__returns_empty_string_if_no_networks(self):
        self.assertEqual("", get_trusted_networks())

    def test__returns_single_network(self):
        net = factory.make_Network()
        expected = unicode(net.get_network().cidr) + ';'
        self.assertEqual(expected, get_trusted_networks())

    def test__returns_many_networks(self):
        nets = [factory.make_Network() for _ in xrange(random.randint(1, 5))]
        expected = "; ".join(unicode(net.get_network().cidr) for net in nets)
        expected += ';'
        self.assertEqual(expected, get_trusted_networks())
