# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ZoneGenerator` and supporting cast."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import socket

from django.conf import settings
from maasserver import server_address
from maasserver.dns import zonegenerator
from maasserver.dns.zonegenerator import (
    DNSException,
    get_dns_server_address,
    get_hostname_ip_mapping,
    lazydict,
    warn_loopback,
    WARNING_MESSAGE,
    ZoneGenerator,
)
from maasserver.enum import (
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockNotCalled,
)
from mock import (
    ANY,
    call,
    Mock,
)
from netaddr import IPNetwork
from provisioningserver.dns.config import SRVRecord
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
)
from provisioningserver.utils.enum import (
    map_enum,
    map_enum_unique_values,
)
from testtools import TestCase
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
    MatchesSetwise,
    MatchesStructure,
)


class TestGetDNSServerAddress(MAASServerTestCase):

    def patch_DEFAULT_MAAS_URL(self, hostname=None):
        """Replace `DEFAULT_MAAS_URL` with a randomised URL."""
        self.patch(
            settings, 'DEFAULT_MAAS_URL', factory.make_url(netloc=hostname))

    def test_get_dns_server_address_resolves_hostname(self):
        ip = factory.make_ipv4_address()
        resolver = self.patch(server_address, 'resolve_hostname')
        resolver.return_value = {ip}
        hostname = factory.make_hostname()
        self.patch_DEFAULT_MAAS_URL(hostname=hostname)
        result = get_dns_server_address()
        self.assertEqual(ip, result)
        self.expectThat(resolver, MockAnyCall(hostname, 4))
        self.expectThat(resolver, MockAnyCall(hostname, 6))

    def test_get_dns_server_address_passes_on_IPv4_IPv6_selection(self):
        ipv4 = factory.pick_bool()
        ipv6 = factory.pick_bool()
        patch = self.patch(zonegenerator, 'get_maas_facing_server_address')
        patch.return_value = factory.make_ipv4_address()

        get_dns_server_address(ipv4=ipv4, ipv6=ipv6)

        self.assertThat(patch, MockCalledOnceWith(ANY, ipv4=ipv4, ipv6=ipv6))

    def test_get_dns_server_address_raises_if_hostname_doesnt_resolve(self):
        self.patch(
            zonegenerator, 'get_maas_facing_server_address',
            FakeMethod(failure=socket.error))
        self.patch_DEFAULT_MAAS_URL()
        self.assertRaises(DNSException, get_dns_server_address)

    def test_get_dns_server_address_logs_warning_if_ip_is_localhost(self):
        logger = self.patch(zonegenerator, 'logger')
        self.patch(
            zonegenerator, 'get_maas_facing_server_address',
            Mock(return_value='127.0.0.1'))
        get_dns_server_address()
        self.assertEqual(
            call(WARNING_MESSAGE % '127.0.0.1'),
            logger.warn.call_args)

    def test_get_dns_server_address_uses_nodegroup_maas_url(self):
        ip = factory.make_ipv4_address()
        resolver = self.patch(server_address, 'resolve_hostname')
        resolver.return_value = {ip}
        hostname = factory.make_hostname()
        maas_url = 'http://%s' % hostname
        nodegroup = factory.make_NodeGroup(maas_url=maas_url)
        result = get_dns_server_address(nodegroup)
        self.expectThat(ip, Equals(result))
        self.expectThat(resolver, MockAnyCall(hostname, 4))
        self.expectThat(resolver, MockAnyCall(hostname, 6))


class TestWarnLoopback(MAASServerTestCase):
    def test_warn_loopback_warns_about_IPv4_loopback(self):
        logger = self.patch(zonegenerator, 'logger')
        loopback = '127.0.0.1'
        warn_loopback(loopback)
        self.assertThat(
            logger.warn, MockCalledOnceWith(WARNING_MESSAGE % loopback))

    def test_warn_loopback_warns_about_any_IPv4_loopback(self):
        logger = self.patch(zonegenerator, 'logger')
        loopback = '127.254.100.99'
        warn_loopback(loopback)
        self.assertThat(logger.warn, MockCalledOnceWith(ANY))

    def test_warn_loopback_warns_about_IPv6_loopback(self):
        logger = self.patch(zonegenerator, 'logger')
        loopback = '::1'
        warn_loopback(loopback)
        self.assertThat(logger.warn, MockCalledOnceWith(ANY))

    def test_warn_loopback_does_not_warn_about_sensible_IPv4(self):
        logger = self.patch(zonegenerator, 'logger')
        warn_loopback('10.1.2.3')
        self.assertThat(logger.warn, MockNotCalled())

    def test_warn_loopback_does_not_warn_about_sensible_IPv6(self):
        logger = self.patch(zonegenerator, 'logger')
        warn_loopback('1::9')
        self.assertThat(logger.warn, MockNotCalled())


class TestLazyDict(TestCase):
    """Tests for `lazydict`."""

    def test_empty_initially(self):
        self.assertEqual({}, lazydict(Mock()))

    def test_populates_on_demand(self):
        value = factory.make_name('value')
        value_dict = lazydict(lambda key: value)
        key = factory.make_name('key')
        retrieved_value = value_dict[key]
        self.assertEqual(value, retrieved_value)
        self.assertEqual({key: value}, value_dict)

    def test_remembers_elements(self):
        value_dict = lazydict(lambda key: factory.make_name('value'))
        key = factory.make_name('key')
        self.assertEqual(value_dict[key], value_dict[key])

    def test_holds_one_value_per_key(self):
        value_dict = lazydict(lambda key: key)
        key1 = factory.make_name('key')
        key2 = factory.make_name('key')

        value1 = value_dict[key1]
        value2 = value_dict[key2]

        self.assertEqual((key1, key2), (value1, value2))
        self.assertEqual({key1: key1, key2: key2}, value_dict)


class TestGetHostnameIPMapping(MAASServerTestCase):
    """Test for `get_hostname_ip_mapping`."""

    def test_get_hostname_ip_mapping_combines_mappings(self):
        nodegroup = factory.make_NodeGroup()
        # Create dynamic mapping for a deployed node.
        node1 = factory.make_Node(
            nodegroup=nodegroup, status=NODE_STATUS.DEPLOYED)
        mac = factory.make_MACAddress(node=node1)
        lease = factory.make_DHCPLease(
            nodegroup=nodegroup, mac=mac.mac_address)
        # Create static mapping for an allocated node.
        node2 = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            nodegroup=nodegroup)
        staticip = factory.make_StaticIPAddress(mac=node2.get_primary_mac())

        expected_mapping = {
            node1.hostname: [lease.ip],
            node2.hostname: [staticip.ip],
        }
        self.assertEqual(
            expected_mapping, get_hostname_ip_mapping(nodegroup))

    def test_get_hostname_ip_mapping_gives_precedence_to_static_mappings(self):
        nodegroup = factory.make_NodeGroup()
        # Create dynamic mapping for an allocated node.
        node = factory.make_Node(
            nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED,
            disable_ipv4=False)
        mac = factory.make_MACAddress(node=node)
        factory.make_DHCPLease(
            nodegroup=nodegroup, mac=mac.mac_address)
        # Create static mapping for the *same* node.
        staticip = factory.make_StaticIPAddress(mac=node.get_primary_mac())

        self.assertEqual(
            {node.hostname: [staticip.ip]},
            get_hostname_ip_mapping(nodegroup))

    def test_get_hostname_ip_mapping_includes_IPv4_and_IPv6_by_default(self):
        # A node can have static IP addresses for IPv4 and IPv6 both.
        # (It can't have DHCP leases for IPv6, since we don't parse or use
        # those.)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            status=NODE_STATUS.ALLOCATED, disable_ipv4=False)
        mac = node.get_primary_mac()
        ipv4 = factory.make_ipv4_address()
        ipv6 = factory.make_ipv6_address()
        factory.make_StaticIPAddress(mac=mac, ip=ipv4)
        factory.make_StaticIPAddress(mac=mac, ip=ipv6)

        self.assertItemsEqual(
            [ipv4, ipv6],
            get_hostname_ip_mapping(node.nodegroup)[node.hostname])

    def test_get_hostname_ip_mapping_excludes_IPv4_if_disabled_on_node(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            status=NODE_STATUS.ALLOCATED, disable_ipv4=True)
        mac = node.get_primary_mac()
        ipv4 = factory.make_ipv4_address()
        ipv6 = factory.make_ipv6_address()
        factory.make_StaticIPAddress(mac=mac, ip=ipv4)
        factory.make_StaticIPAddress(mac=mac, ip=ipv6)

        self.assertItemsEqual(
            [ipv6],
            get_hostname_ip_mapping(node.nodegroup)[node.hostname])

    def test_get_hostname_ip_mapping_disables_IPv4_per_individual_node(self):
        nodegroup = factory.make_NodeGroup()
        node_with_ipv4 = (
            factory.make_Node_with_MACAddress_and_NodeGroupInterface(
                nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED,
                disable_ipv4=False))
        node_without_ipv4 = (
            factory.make_Node_with_MACAddress_and_NodeGroupInterface(
                nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED,
                disable_ipv4=True))
        ipv4 = factory.make_ipv4_address()
        factory.make_StaticIPAddress(
            mac=node_with_ipv4.get_primary_mac(), ip=ipv4)
        factory.make_StaticIPAddress(
            mac=node_without_ipv4.get_primary_mac())

        mappings = get_hostname_ip_mapping(nodegroup)
        # The node with IPv4 enabled gets its IPv4 address mapped.
        # The node with IPv4 disabled gets no mapping.
        self.assertEqual({node_with_ipv4.hostname: [ipv4]}, mappings)


def forward_zone(domain):
    """Create a matcher for a :class:`DNSForwardZoneConfig`.

    Returns a matcher which asserts that the test value is a
    `DNSForwardZoneConfig` with the given domain.
    """
    return MatchesAll(
        IsInstance(DNSForwardZoneConfig),
        MatchesStructure.byEquality(domain=domain))


def reverse_zone(domain, network):
    """Create a matcher for a :class:`DNSReverseZoneConfig`.

    Returns a matcher which asserts that the test value is a
    :class:`DNSReverseZoneConfig` with the given domain and network.
    """
    network = network if network is None else IPNetwork(network)
    return MatchesAll(
        IsInstance(DNSReverseZoneConfig),
        MatchesStructure.byEquality(
            domain=domain, _network=network))


class TestZoneGenerator(MAASServerTestCase):
    """Tests for :class:x`ZoneGenerator`."""

    def make_node_group(self, **kwargs):
        """Create an accepted nodegroup with a managed interface."""
        return factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS, **kwargs)

    def test_get_forward_nodegroups_returns_empty_for_unknown_domain(self):
        self.assertEqual(
            set(),
            ZoneGenerator._get_forward_nodegroups(
                factory.make_name('domain')))

    def test_get_forward_nodegroups_returns_empty_for_no_domains(self):
        self.assertEqual(set(), ZoneGenerator._get_forward_nodegroups([]))

    def test_get_forward_nodegroups_returns_dns_managed_nodegroups(self):
        domain = factory.make_name('domain')
        nodegroup = self.make_node_group(name=domain)
        self.assertEqual(
            {nodegroup},
            ZoneGenerator._get_forward_nodegroups([domain]))

    def test_get_forward_nodegroups_includes_multiple_domains(self):
        nodegroups = [self.make_node_group() for _ in range(3)]
        self.assertEqual(
            set(nodegroups),
            ZoneGenerator._get_forward_nodegroups(
                [nodegroup.name for nodegroup in nodegroups]))

    def test_get_forward_nodegroups_ignores_non_dns_nodegroups(self):
        domain = factory.make_name('domain')
        managed_nodegroup = self.make_node_group(name=domain)
        factory.make_NodeGroup(
            name=domain, status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        factory.make_NodeGroup(
            name=domain, status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertEqual(
            {managed_nodegroup},
            ZoneGenerator._get_forward_nodegroups([domain]))

    def test_get_forward_nodegroups_ignores_other_domains(self):
        nodegroups = [self.make_node_group() for _ in range(2)]
        self.assertEqual(
            {nodegroups[0]},
            ZoneGenerator._get_forward_nodegroups([nodegroups[0].name]))

    def test_get_forward_nodegroups_ignores_unaccepted_nodegroups(self):
        domain = factory.make_name('domain')
        nodegroups = {
            status: factory.make_NodeGroup(
                status=status, name=domain,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            for status in map_enum_unique_values(NODEGROUP_STATUS).values()
            }
        self.assertEqual(
            {nodegroups[NODEGROUP_STATUS.ENABLED]},
            ZoneGenerator._get_forward_nodegroups([domain]))

    def test_get_reverse_nodegroups_returns_only_dns_managed_nodegroups(self):
        nodegroups = {
            management: factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ENABLED, management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            }
        self.assertEqual(
            {nodegroups[NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS]},
            ZoneGenerator._get_reverse_nodegroups(nodegroups.values()))

    def test_get_reverse_nodegroups_ignores_other_nodegroups(self):
        nodegroups = [self.make_node_group() for _ in range(3)]
        self.assertEqual(
            {nodegroups[0]},
            ZoneGenerator._get_reverse_nodegroups(nodegroups[:1]))

    def test_get_reverse_nodegroups_ignores_unaccepted_nodegroups(self):
        nodegroups = {
            status: factory.make_NodeGroup(
                status=status,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
            for status in map_enum(NODEGROUP_STATUS).values()
            }
        self.assertEqual(
            {nodegroups[NODEGROUP_STATUS.ENABLED]},
            ZoneGenerator._get_reverse_nodegroups(nodegroups.values()))

    def test_get_networks_returns_network(self):
        nodegroup = self.make_node_group()
        [interface] = nodegroup.get_managed_interfaces()
        networks_dict = ZoneGenerator._get_networks()
        retrieved_interface = networks_dict[nodegroup]
        self.assertEqual(
            [
                (
                    interface.network,
                    (interface.ip_range_low, interface.ip_range_high)
                )
            ],
            retrieved_interface)

    def test_get_networks_returns_multiple_networks(self):
        nodegroups = [self.make_node_group() for _ in range(3)]
        networks_dict = ZoneGenerator._get_networks()
        for nodegroup in nodegroups:
            [interface] = nodegroup.get_managed_interfaces()
            self.assertEqual(
                [
                    (
                        interface.network,
                        (interface.ip_range_low, interface.ip_range_high),
                    ),
                ],
                networks_dict[nodegroup])

    def test_get_networks_returns_managed_networks(self):
        nodegroups = [
            factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ENABLED, management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            ]
        networks_dict = ZoneGenerator._get_networks()
        # Force lazydict to evaluate for all these nodegroups.
        for nodegroup in nodegroups:
            networks_dict[nodegroup]
        self.assertEqual(
            {
                nodegroup: [
                    (
                        interface.network,
                        (interface.ip_range_low, interface.ip_range_high),
                    )
                    for interface in nodegroup.get_managed_interfaces()
                    ]
                for nodegroup in nodegroups
            },
            networks_dict)

    def test_get_srv_mappings_returns_empty_list_when_no_windows_kms(self):
        Config.objects.set_config("windows_kms_host", None)
        self.assertItemsEqual([], ZoneGenerator._get_srv_mappings())

    def test_get_srv_mappings_returns_kms_srv_record(self):
        hostname = factory.make_name('hostname')
        Config.objects.set_config("windows_kms_host", hostname)
        srv = SRVRecord(
            service='_vlmcs._tcp', port=1688, target=hostname,
            priority=0, weight=0)
        self.assertItemsEqual([srv], ZoneGenerator._get_srv_mappings())

    def test_with_no_nodegroups_yields_nothing(self):
        self.assertEqual([], ZoneGenerator((), Mock()).as_list())

    def test_with_one_nodegroup_yields_forward_and_reverse_zone(self):
        nodegroup = self.make_node_group(
            name="henry", network=IPNetwork("10/32"))
        zones = ZoneGenerator(nodegroup, Mock()).as_list()
        self.assertThat(
            zones, MatchesSetwise(
                forward_zone("henry"),
                reverse_zone("henry", "10/32")))

    def test_two_managed_interfaces_yields_one_forward_two_reverse_zones(self):
        nodegroup = self.make_node_group()
        factory.make_NodeGroupInterface(
            nodegroup=nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        [interface1, interface2] = nodegroup.get_managed_interfaces()

        expected_zones = [
            forward_zone(nodegroup.name),
            reverse_zone(nodegroup.name, interface1.network),
            reverse_zone(nodegroup.name, interface2.network),
            ]
        self.assertThat(
            ZoneGenerator([nodegroup], Mock()).as_list(),
            MatchesSetwise(*expected_zones))

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
            forward_zone("one"),
            forward_zone("two"),
            # For the reverse zones, a single reverse zone description is
            # generated for each nodegroup passed in, in network order.
            reverse_zone("one", "10/32"),
            reverse_zone("one", "11/32"),
            reverse_zone("two", "20/32"),
            reverse_zone("two", "21/32"),
            )
        self.assertThat(
            ZoneGenerator(nodegroups, Mock()).as_list(),
            MatchesSetwise(*expected_zones))
