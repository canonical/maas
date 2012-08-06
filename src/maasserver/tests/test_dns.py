# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test DNS module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


from itertools import islice
import random
import socket

from django.conf import settings
from django.core.management import call_command
from maasserver import (
    dns,
    server_address,
    )
from maasserver.models import Config
from maasserver.models.dhcplease import (
    DHCPLease,
    post_updates,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maastesting.bindfixture import BINDServer
from maastesting.celery import CeleryFixture
from maastesting.fakemethod import FakeMethod
from maastesting.tests.test_bindfixture import dig_call
from netaddr import (
    IPNetwork,
    IPRange,
    )
from provisioningserver.dns.config import (
    conf,
    DNSZoneConfig,
    )
from provisioningserver.dns.utils import generated_hostname
from rabbitfixture.server import allocate_ports
from testresources import FixtureResource
from testtools.matchers import MatchesStructure


class TestDNSUtilities(TestCase):

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
        hostname = factory.getRandomString().lower()
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

    def test_get_zone_creates_DNSZoneConfig(self):
        nodegroup = factory.make_node_group()
        serial = random.randint(1, 100)
        zone = dns.get_zone(nodegroup, serial)
        self.assertAttributes(
            zone,
            dict(
                zone_name=nodegroup.name,
                serial=serial,
                subnet_mask=nodegroup.subnet_mask,
                broadcast_ip=nodegroup.broadcast_ip,
                ip_range_low=nodegroup.ip_range_low,
                ip_range_high=nodegroup.ip_range_high,
                mapping=DHCPLease.objects.get_hostname_ip_mapping(nodegroup),
                ))

    def test_get_zone_returns_None_if_dhcp_not_enabled(self):
        nodegroup = factory.make_node_group()
        nodegroup.subnet_mask = None
        nodegroup.save()
        self.assertIsNone(dns.get_zone(nodegroup))


class TestDNSConfigModifications(TestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def setUp(self):
        super(TestDNSConfigModifications, self).setUp()
        self.bind = self.useFixture(BINDServer())
        self.patch(conf, 'DNS_CONFIG_DIR', self.bind.config.homedir)

        # Use a random port for rndc.
        self.patch(conf, 'DNS_RNDC_PORT', allocate_ports(1)[0])
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

    def create_nodegroup_with_lease(self, lease_number=1, nodegroup=None):
        if nodegroup is None:
            nodegroup = factory.make_node_group(
                network=IPNetwork('192.168.0.1/24'))
        node = factory.make_node(
            nodegroup=nodegroup, set_hostname=True)
        mac = factory.make_mac_address(node=node)
        ips = IPRange(nodegroup.ip_range_low, nodegroup.ip_range_high)
        lease_ip = str(islice(ips, lease_number, lease_number + 1).next())
        lease = factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=mac.mac_address, ip=lease_ip)
        # Simulate that this lease was created by
        # DHCPLease.objects.update_leases: fire the 'post_updates'
        # signal.
        post_updates.send(sender=DHCPLease.objects)
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
        dns.add_zone(nodegroup)
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_add_zone_doesnt_write_config_if_dhcp_disabled(self):
        recorder = FakeMethod()
        self.patch(DNSZoneConfig, 'write_config', recorder)
        nodegroup = factory.make_node_group()
        nodegroup.subnet_mask = None
        nodegroup.save()
        dns.add_zone(nodegroup)
        self.assertEqual(0, recorder.call_count)

    def test_change_dns_zone_changes_dns_zone(self):
        nodegroup, _, _ = self.create_nodegroup_with_lease()
        dns.write_full_dns_config()
        nodegroup, new_node, new_lease = (
            self.create_nodegroup_with_lease(
                nodegroup=nodegroup, lease_number=2))
        dns.change_dns_zones(nodegroup)
        self.assertDNSMatches(new_node.hostname, nodegroup.name, new_lease.ip)

    def test_is_dns_enabled_return_false_if_DNS_CONNECT_False(self):
        self.patch(settings, 'DNS_CONNECT', False)
        self.assertFalse(dns.is_dns_enabled())

    def test_is_dns_enabled_return_false_if_confif_enable_dns_False(self):
        Config.objects.set_config('enable_dns', False)
        self.assertFalse(dns.is_dns_enabled())

    def test_is_dns_enabled_return_True(self):
        self.patch(settings, 'DNS_CONNECT', True)
        Config.objects.set_config('enable_dns', True)
        self.assertTrue(dns.is_dns_enabled())

    def test_change_dns_zone_changes_doesnt_write_conf_if_dhcp_disabled(self):
        recorder = FakeMethod()
        self.patch(DNSZoneConfig, 'write_config', recorder)
        nodegroup = factory.make_node_group()
        nodegroup.subnet_mask = None
        nodegroup.save()
        dns.change_dns_zones(nodegroup)
        self.assertEqual(0, recorder.call_count)

    def test_write_full_dns_doesnt_write_config_if_dhcp_disabled(self):
        recorder = FakeMethod()
        self.patch(DNSZoneConfig, 'write_config', recorder)
        nodegroup = factory.make_node_group()
        nodegroup.subnet_mask = None
        nodegroup.save()
        dns.write_full_dns_config()
        self.assertEqual(0, recorder.call_count)

    def test_write_full_dns_loads_full_dns_config(self):
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        dns.write_full_dns_config()
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_write_full_dns_can_write_inactive_config(self):
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        dns.write_full_dns_config(active=False)
        self.assertEqual([''], self.dig_resolve(generated_hostname(lease.ip)))

    def test_dns_config_has_NS_record(self):
        ip = factory.getRandomIPAddress()
        self.patch(settings, 'DEFAULT_MAAS_URL', 'http://%s/' % ip)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        dns.write_full_dns_config()
        # Get the NS record for the zone 'nodegroup.name'.
        ns_record = dig_call(
            port=self.bind.config.port,
            commands=[nodegroup.name, 'NS', '+short'])
        # Resolve that hostname.
        ip_of_ns_record = dig_call(
            port=self.bind.config.port, commands=[ns_record, '+short'])
        self.assertEqual(ip, ip_of_ns_record)

    def test_is_dns_enabled_follows_DNS_CONNECT(self):
        rand_bool = factory.getRandomBoolean()
        self.patch(settings, "DNS_CONNECT", rand_bool)
        self.assertEqual(rand_bool, dns.is_dns_enabled())

    def test_add_nodegroup_creates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.getRandomIPInNetwork(network)
        nodegroup = factory.make_node_group(network=network)
        self.assertDNSMatches(generated_hostname(ip), nodegroup.name, ip)

    def test_edit_nodegroup_updates_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        old_network = IPNetwork('192.168.7.1/24')
        old_ip = factory.getRandomIPInNetwork(old_network)
        nodegroup = factory.make_node_group(network=old_network)
        # Edit nodegroup's network information to '192.168.44.1/24'
        nodegroup.broadcast_ip = '192.168.44.255'
        nodegroup.netmask = '255.255.255.0'
        nodegroup.ip_range_low = '192.168.44.0'
        nodegroup.ip_range_high = '192.168.44.255'
        nodegroup.save()
        ip = factory.getRandomIPInNetwork(IPNetwork('192.168.44.1/24'))
        # The ip from the old network does not resolve anymore.
        self.assertEqual([''], self.dig_resolve(generated_hostname(old_ip)))
        self.assertEqual([''], self.dig_reverse_resolve(old_ip))
        # The ip from the new network resolves.
        self.assertDNSMatches(generated_hostname(ip), nodegroup.name, ip)

    def test_delete_nodegroup_disables_DNS_zone(self):
        self.patch(settings, "DNS_CONNECT", True)
        network = IPNetwork('192.168.7.1/24')
        ip = factory.getRandomIPInNetwork(network)
        nodegroup = factory.make_node_group(network=network)
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
        self.patch(DNSZoneConfig, 'write_config', recorder)
        node.error = factory.getRandomString()
        node.save()
        self.assertEqual(0, recorder.call_count)

    def test_change_config_enable_dns_enables_dns(self):
        self.patch(settings, "DNS_CONNECT", False)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        settings.DNS_CONNECT = True
        Config.objects.set_config('enable_dns', True)
        self.assertDNSMatches(node.hostname, nodegroup.name, lease.ip)

    def test_change_config_enable_dns_disables_dns(self):
        self.patch(settings, "DNS_CONNECT", True)
        nodegroup, node, lease = self.create_nodegroup_with_lease()
        Config.objects.set_config('enable_dns', False)
        self.assertEqual([''], self.dig_resolve(generated_hostname(lease.ip)))
