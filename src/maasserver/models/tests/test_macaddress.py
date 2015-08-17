# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`MACAddress` tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from operator import attrgetter
import random

from django.core.exceptions import ValidationError
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.exceptions import (
    StaticIPAddressConflict,
    StaticIPAddressForbidden,
    StaticIPAddressTypeClash,
    StaticIPAddressUnavailable,
)
from maasserver.forms import create_Network_from_NodeGroupInterface
from maasserver.models import (
    NodeGroupInterface,
    StaticIPAddress,
)
from maasserver.models.macaddress import (
    find_cluster_interface_responsible_for_ip,
    MACAddress,
    update_mac_cluster_interfaces,
    update_macs_cluster_interfaces,
)
from maasserver.models.network import Network
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    MatchesStructure,
    Not,
)


def get_random_ip_from_interface_range(interface, use_static_range=None):
    """Return a random IP from the pool available to an interface.

    :return: An IP address as a string."""
    if use_static_range:
        ip_range = IPRange(
            interface.static_ip_range_low, interface.static_ip_range_high)
    else:
        ip_range = IPRange(
            interface.ip_range_low, interface.ip_range_high)
    chosen_ip = random.choice(ip_range)
    return unicode(chosen_ip)


class MACAddressTest(MAASServerTestCase):

    def test_stores_to_database(self):
        mac = factory.make_MACAddress_with_Node()
        self.assertEqual([mac], list(MACAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        mac = MACAddress(
            mac_address='aa:bb:ccxdd:ee:ff', node=factory.make_Node())
        self.assertRaises(ValidationError, mac.full_clean)

    def test_mac_not_in_any_network_by_default(self):
        mac = factory.make_MACAddress_with_Node()
        self.assertItemsEqual([], mac.networks.all())

    def test_mac_can_be_connected_to_multiple_networks(self):
        networks = factory.make_Networks(3)
        mac = factory.make_MACAddress_with_Node(networks=networks)
        self.assertItemsEqual(networks, reload_object(mac).networks.all())

    def test_get_networks_returns_empty_if_no_networks(self):
        mac = factory.make_MACAddress_with_Node(networks=[])
        self.assertEqual([], list(mac.get_networks()))

    def test_get_networks_returns_networks(self):
        network = factory.make_Network()
        mac = factory.make_MACAddress_with_Node(networks=[network])
        self.assertEqual([network], list(mac.get_networks()))

    def test_get_networks_sorts_by_network_name(self):
        networks = factory.make_Networks(3, sortable_name=True)
        mac = factory.make_MACAddress_with_Node(networks=networks)
        self.assertEqual(
            sorted(networks, key=attrgetter('name')),
            list(mac.get_networks()))

    def test_unicode_copes_with_unclean_unicode_mac_address(self):
        # If MACAddress.mac_address has not been cleaned yet, it will
        # contain a string rather than a MAC.  Make sure __unicode__
        # handles this.
        mac_str = "aa:bb:cc:dd:ee:ff"
        mac = MACAddress(
            mac_address=mac_str, node=factory.make_Node())
        self.assertEqual(mac_str, unicode(mac))

    def test_unicode_copes_with_unclean_bytes_mac_address(self):
        # If MACAddress.mac_address has not been cleaned yet, it will
        # contain a string rather than a MAC.  Make sure __str__
        # handles this.
        bytes_mac = bytes("aa:bb:cc:dd:ee:ff")
        mac = MACAddress(
            mac_address=bytes_mac, node=factory.make_Node())
        self.assertEqual(bytes_mac, mac.__str__())

    def test_cluster_interface_deletion_does_not_delete_MAC(self):
        cluster_interface = factory.make_NodeGroupInterface(
            factory.make_NodeGroup())
        mac_address = factory.make_MACAddress(
            cluster_interface=cluster_interface)
        cluster_interface.delete()
        self.expectThat(reload_object(mac_address), Not(Is(None)))

    def test_get_cluster_interface_returns_cluster_interface(self):
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        self.assertEqual(mac.cluster_interface, mac.get_cluster_interface())

    def test_get_cluster_interface_returns_parent_cluster_interface(self):
        parent = make_node_attached_to_cluster_interfaces()
        node = factory.make_Node(parent=parent, mac=True, installable=False)
        mac = node.get_primary_mac()
        self.assertEqual(
            parent.get_primary_mac().cluster_interface,
            mac.get_cluster_interface())


class TestFindClusterInterfaceResponsibleFor(MAASServerTestCase):
    """Tests for `find_cluster_interface_responsible_for_ip`."""

    def test__returns_None_if_no_interfaces(self):
        ip = factory.make_ipv4_address()
        self.assertIsNone(find_cluster_interface_responsible_for_ip([], ip))

    def test__returns_None_if_no_interface_networks(self):
        nodegroup = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(nodegroup, network=None)
        ip = factory.make_ipv4_address()
        self.assertIsNone(find_cluster_interface_responsible_for_ip([], ip))

    def test__finds_responsible_IPv4_interface(self):
        nodegroup = factory.make_NodeGroup()
        networks = [
            IPNetwork('10.1.1.0/24'),
            IPNetwork('10.2.2.0/24'),
            IPNetwork('10.3.3.0/24')
            ]
        interfaces = [
            factory.make_NodeGroupInterface(nodegroup, network=network)
            for network in networks
            ]
        self.assertEqual(
            interfaces[1],
            find_cluster_interface_responsible_for_ip(
                interfaces, IPAddress('10.2.2.100')))

    def test__finds_responsible_IPv6_interface(self):
        nodegroup = factory.make_NodeGroup()
        networks = [
            IPNetwork('2001:1::/64'),
            IPNetwork('2001:2::/64'),
            IPNetwork('2001:3::/64'),
            ]
        interfaces = [
            factory.make_NodeGroupInterface(nodegroup, network=network)
            for network in networks
            ]
        self.assertEqual(
            interfaces[1],
            find_cluster_interface_responsible_for_ip(
                interfaces, IPAddress('2001:2::100')))

    def test__returns_None_if_none_match(self):
        nodegroup = factory.make_NodeGroup()
        networks = [
            IPNetwork('10.1.1.0/24'),
            IPNetwork('10.2.2.0/24'),
            IPNetwork('10.3.3.0/24'),
            ]
        interfaces = [
            factory.make_NodeGroupInterface(nodegroup, network=network)
            for network in networks
            ]
        self.assertIsNone(
            find_cluster_interface_responsible_for_ip(
                interfaces, IPAddress('10.9.9.1')))

    def test__combines_IPv4_and_IPv6(self):
        nodegroup = factory.make_NodeGroup()
        networks = [
            IPNetwork('10.1.1.0/24'),
            IPNetwork('2001:2::/64'),
            IPNetwork('10.3.3.0/24'),
            ]
        interfaces = [
            factory.make_NodeGroupInterface(nodegroup, network=network)
            for network in networks
            ]
        self.assertEqual(
            interfaces[2],
            find_cluster_interface_responsible_for_ip(
                interfaces, IPAddress('10.3.3.100')))


def find_cluster_interface(cluster, ip_version):
    """Find cluster interface for `cluster` with the given IP version.

    :param cluster: A `NodeGroup`.
    :param ip_version: Either 4 or 6 to find IPv4 or IPv6 cluster
        interfaces, respectively.
    :return: Either a single matching `NodeGroupInterface`, or `None`.
    """
    for interface in cluster.nodegroupinterface_set.all():
        if IPAddress(interface.ip).version == ip_version:
            return interface
    return None


def make_node_attached_to_cluster_interfaces(ipv4_network=None,
                                             ipv6_network=None):
    """Return a `Node` with a `MACAddress` on IPv4 & IPv6 interfaces."""
    if ipv4_network is None:
        ipv4_network = factory.make_ipv4_network()
    if ipv6_network is None:
        ipv6_network = factory.make_ipv6_network()
    node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
        network=ipv4_network)
    # The IPv6 cluster interface must be for the same network interface
    # as the IPv4 one; that's how we know the MAC is attached to both.
    ipv4_interface = find_cluster_interface(node.nodegroup, 4)
    factory.make_NodeGroupInterface(
        node.nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
        network=ipv6_network, interface=ipv4_interface.interface)
    return node


class TestMapAllocatedAddresses(MAASServerTestCase):
    """Tests for `_map_allocated_addresses`."""

    def test__returns_empty_if_no_interfaces_given(self):
        mac = factory.make_MACAddress_with_Node()
        self.assertEqual({}, mac._map_allocated_addresses([]))

    def test__maps_interface_without_allocation_to_None(self):
        cluster = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(cluster)
        mac = factory.make_MACAddress_with_Node(cluster_interface=interface)
        self.assertEqual(
            {interface: None},
            mac._map_allocated_addresses([interface]))

    def test__maps_interface_to_allocated_static_IPv4_address(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            network=factory.make_ipv4_network())
        interface = find_cluster_interface(node.nodegroup, 4)
        mac = node.get_primary_mac()
        sip = factory.make_StaticIPAddress(
            mac=mac, ip=interface.static_ip_range_low)

        self.assertEqual(
            {interface: sip}, mac._map_allocated_addresses([interface]))

    def test__maps_interface_to_allocated_static_IPv6_address(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            network=factory.make_ipv6_network())
        interface = find_cluster_interface(node.nodegroup, 6)
        mac = node.get_primary_mac()
        sip = factory.make_StaticIPAddress(
            mac=mac, ip=interface.static_ip_range_low)

        self.assertEqual(
            {interface: sip}, mac._map_allocated_addresses([interface]))

    def test__ignores_addresses_for_other_interfaces(self):
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        factory.make_StaticIPAddress(
            mac=mac, ip=ipv4_interface.static_ip_range_low)
        ipv6_sip = factory.make_StaticIPAddress(
            mac=mac, ip=ipv6_interface.static_ip_range_low)

        self.assertEqual(
            {ipv6_interface: ipv6_sip},
            mac._map_allocated_addresses([ipv6_interface]))


class TestAllocateStaticAddress(MAASServerTestCase):
    """Tests for `_allocate_static_address`."""

    def test__allocates_static_IPv4_address(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            network=factory.make_ipv4_network())
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        requested_ip = ipv4_interface.static_ip_range_high

        sip = mac._allocate_static_address(
            ipv4_interface, iptype, requested_address=requested_ip)

        self.expectThat(sip.alloc_type, Equals(iptype))
        self.expectThat(sip.ip, Equals(requested_ip))
        self.assertIn(IPAddress(sip.ip), ipv4_interface.get_static_ip_range())

    def test__allocates_static_IPv6_address(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            network=factory.make_ipv6_network())
        mac = node.get_primary_mac()
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        requested_ip = ipv6_interface.static_ip_range_high

        sip = mac._allocate_static_address(
            ipv6_interface, iptype, requested_address=requested_ip)

        self.expectThat(sip.alloc_type, Equals(iptype))
        self.expectThat(sip.ip, Equals(requested_ip))
        self.assertIn(IPAddress(sip.ip), ipv6_interface.get_static_ip_range())

    def test__links_static_address_to_MAC(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        interface = find_cluster_interface(node.nodegroup, 4)
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])

        sip = mac._allocate_static_address(interface, iptype)

        self.assertItemsEqual([sip], mac.ip_addresses.all())


def pick_two_allocation_types():
    """Pick two different allocation types other than `USER_RESERVED`.

    The reason not to use `USER_RESERVED` is that an allocation of that
    type requires a `user` argument, which the other types don't accept.
    """
    iptype1 = factory.pick_enum(
        IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
    iptype2 = factory.pick_enum(
        IPADDRESS_TYPE, but_not=[iptype1, IPADDRESS_TYPE.USER_RESERVED])
    return iptype1, iptype2


class TestClaimStaticIPs(MAASServerTestCase):
    """Tests for `MACAddress.claim_static_ips`."""

    def test__returns_empty_if_no_cluster_interface(self):
        # If mac.cluster_interface is None, we can't allocate any IP.
        mac = factory.make_MACAddress_with_Node()
        self.assertEquals([], mac.claim_static_ips(update_host_maps=False))

    def test__reserves_an_ip_address(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        [claimed_ip] = mac.claim_static_ips(update_host_maps=False)
        self.assertIsInstance(claimed_ip, StaticIPAddress)
        self.assertNotEqual([], list(node.static_ip_addresses()))
        self.assertEqual(
            IPADDRESS_TYPE.AUTO, StaticIPAddress.objects.all()[0].alloc_type)

    def test__allocates_on_all_relevant_cluster_interfaces(self):
        ipv4_network = factory.make_ipv4_network()
        ipv6_network = factory.make_ipv6_network()
        node = make_node_attached_to_cluster_interfaces(
            ipv4_network=ipv4_network, ipv6_network=ipv6_network)

        allocation = node.get_primary_mac().claim_static_ips(
            update_host_maps=False)

        # Allocated one IPv4 address and one IPv6 address.
        self.assertThat(allocation, HasLength(2))
        [ipv4_addr, ipv6_addr] = sorted(
            [IPAddress(sip.ip) for sip in allocation],
            key=attrgetter('version'))
        self.assertEqual((4, 6), (ipv4_addr.version, ipv6_addr.version))
        self.assertIn(ipv4_addr, ipv4_network)
        self.assertIn(ipv6_addr, ipv6_network)

    def test__sets_type_as_required(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        [claimed_ip] = mac.claim_static_ips(
            alloc_type=IPADDRESS_TYPE.STICKY, update_host_maps=False)
        self.assertEqual(IPADDRESS_TYPE.STICKY, claimed_ip.alloc_type)

    def test__returns_empty_if_no_static_range_defined(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        mac.cluster_interface.static_ip_range_low = None
        mac.cluster_interface.static_ip_range_high = None
        mac.cluster_interface.save()
        self.assertEqual([], mac.claim_static_ips(update_host_maps=False))

    def test__returns_only_addresses_for_interfaces_with_static_ranges(self):
        ipv6_network = factory.make_ipv6_network()
        node = make_node_attached_to_cluster_interfaces(
            ipv6_network=ipv6_network)
        ipv6_interface = NodeGroupInterface.objects.get(
            nodegroup=node.nodegroup,
            subnet__cidr=unicode(ipv6_network))
        ipv6_interface.static_ip_range_low = None
        ipv6_interface.static_ip_range_high = None
        ipv6_interface.save()

        allocation = node.get_primary_mac().claim_static_ips(
            update_host_maps=False)
        self.assertThat(allocation, HasLength(1))
        [sip] = allocation
        self.assertEqual(4, IPAddress(sip.ip).version)

    def test__raises_if_clashing_type(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(alloc_type=iptype, update_host_maps=False)
        self.assertRaises(
            StaticIPAddressTypeClash,
            mac.claim_static_ips, alloc_type=iptype2)

    def test__raises_when_requesting_clashing_IPv4(self):
        # If the MAC is attached to IPv4 and IPv6 cluster interfaces but
        # you're requesting a specific IPv4 address, then a clash with an
        # existing IPv4 address results in an error regardless of whether the
        # MAC would have been able to allocate an IPv6 address if asked.
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)

        self.assertRaises(
            StaticIPAddressTypeClash,
            mac.claim_static_ips, alloc_type=iptype2,
            requested_address=(
                IPAddress(ipv4_interface.static_ip_range_low) + 1))

    def test__raises_when_requesting_clashing_IPv6(self):
        # If the MAC is attached to IPv4 and IPv6 cluster interfaces but
        # you're requesting a specific IPv6 address, then a clash with an
        # existing IPv6 address results in an error regardless of whether the
        # MAC would have been able to allocate an IPv4 address if asked.
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv6_interface.static_ip_range_low,
            update_host_maps=False)

        self.assertRaises(
            StaticIPAddressTypeClash,
            mac.claim_static_ips, alloc_type=iptype2,
            requested_address=(
                IPAddress(ipv6_interface.static_ip_range_low) + 1))

    def test__skips_clashing_IPv4_if_able_to_allocate_IPv6(self):
        # If the MAC is attached to IPv4 and IPv6 cluster interfaces, a clash
        # with an existing IPv4 address is ignored as long as an IPv6 address
        # can still be allocated.  No IPv4 address is returned.
        ipv6_network = factory.make_ipv6_network()
        node = make_node_attached_to_cluster_interfaces(
            ipv6_network=ipv6_network)
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)

        allocation = mac.claim_static_ips(
            alloc_type=iptype2, update_host_maps=False)

        self.assertThat(allocation, HasLength(1))
        [sip] = allocation
        self.assertIn(IPAddress(sip.ip), ipv6_network)

    def test__skips_clashing_IPv6_if_able_to_allocate_IPv4(self):
        # If the MAC is attached to IPv4 and IPv6 cluster interfaces, a clash
        # with an existing IPv6 address is ignored as long as an IPv4 address
        # can still be allocated.  No IPv4 address is returned.
        ipv4_network = factory.make_ipv4_network()
        node = make_node_attached_to_cluster_interfaces(
            ipv4_network=ipv4_network)
        mac = node.get_primary_mac()
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv6_interface.static_ip_range_low,
            update_host_maps=False)

        allocation = mac.claim_static_ips(
            alloc_type=iptype2, update_host_maps=False)

        self.assertThat(allocation, HasLength(1))
        [sip] = allocation
        self.assertIn(IPAddress(sip.ip), ipv4_network)

    def test__raises_if_IPv4_and_IPv6_both_clash(self):
        # A double clash for both IPv4 and IPv6 addresses raises
        # StaticIPAddressTypeClash.
        ipv4_network = factory.make_ipv4_network()
        ipv6_network = factory.make_ipv6_network()
        node = make_node_attached_to_cluster_interfaces(
            ipv4_network=ipv4_network, ipv6_network=ipv6_network)
        mac = node.get_primary_mac()
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(alloc_type=iptype, update_host_maps=False)

        self.assertRaises(
            StaticIPAddressTypeClash,
            mac.claim_static_ips, alloc_type=iptype2)

    def test__returns_existing_IPv4_if_IPv6_clashes(self):
        # If the MAC is attached to IPv4 and IPv6 cluster interfaces, there's
        # a clash on the IPv6 address, and there's a pre-existing IPv4 (which
        # is not a clash), just the IPv4 address is returned.
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype, iptype2 = pick_two_allocation_types()
        # Clashing IPv6 address:
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv6_interface.static_ip_range_low,
            update_host_maps=False)
        # Pre-existing, but non-clashing, IPv4 address:
        [ipv4_sip] = mac.claim_static_ips(
            alloc_type=iptype2,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)

        self.assertItemsEqual(
            [ipv4_sip],
            mac.claim_static_ips(alloc_type=iptype2, update_host_maps=False))

    def test__returns_existing_IPv6_if_IPv4_clashes(self):
        # If the MAC is attached to IPv4 and IPv6 cluster interfaces, there's
        # a clash on the IPv4 address, and there's a pre-existing IPv6 (which
        # is not a clash), just the IPv6 address is returned.
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype, iptype2 = pick_two_allocation_types()
        # Clashing IPv4 address:
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)
        # Pre-existing, but non-clashing, IPv6 address:
        [ipv6_sip] = mac.claim_static_ips(
            alloc_type=iptype2,
            requested_address=ipv6_interface.static_ip_range_low,
            update_host_maps=False)

        self.assertItemsEqual(
            [ipv6_sip],
            mac.claim_static_ips(alloc_type=iptype2, update_host_maps=False))

    def test__ignores_clashing_IPv4_when_requesting_IPv6(self):
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)

        allocation = mac.claim_static_ips(
            alloc_type=iptype2,
            requested_address=ipv6_interface.static_ip_range_low,
            update_host_maps=False)

        self.assertThat(allocation, HasLength(1))
        [ipv6_sip] = allocation
        self.assertIn(IPAddress(ipv6_sip.ip), ipv6_interface.network)

    def test__ignores_clashing_IPv6_when_requesting_IPv4(self):
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        iptype, iptype2 = pick_two_allocation_types()
        mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv6_interface.static_ip_range_low,
            update_host_maps=False)

        allocation = mac.claim_static_ips(
            alloc_type=iptype2,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)

        self.assertThat(allocation, HasLength(1))
        [ipv4_sip] = allocation
        self.assertIn(IPAddress(ipv4_sip.ip), ipv4_interface.network)

    def test__returns_existing_if_claiming_same_type(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        [ip] = mac.claim_static_ips(alloc_type=iptype, update_host_maps=False)
        self.assertEqual(
            [ip], mac.claim_static_ips(
                alloc_type=iptype, update_host_maps=False))

    def test__combines_existing_and_new_addresses(self):
        node = make_node_attached_to_cluster_interfaces()
        mac = node.get_primary_mac()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        [ipv4_sip] = mac.claim_static_ips(
            alloc_type=iptype,
            requested_address=ipv4_interface.static_ip_range_low,
            update_host_maps=False)

        allocation = mac.claim_static_ips(
            alloc_type=iptype, update_host_maps=False)

        self.assertIn(ipv4_sip, allocation)
        self.assertThat(allocation, HasLength(2))

    def test__passes_requested_ip(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        mac = node.get_primary_mac()
        ip = node.get_primary_mac().cluster_interface.static_ip_range_high
        [allocation] = mac.claim_static_ips(
            requested_address=ip, update_host_maps=False)
        self.assertEqual(ip, allocation.ip)

    def test__allocates_only_IPv4_if_IPv4_address_requested(self):
        node = make_node_attached_to_cluster_interfaces()
        ipv4_interface = find_cluster_interface(node.nodegroup, 4)
        requested_ip = ipv4_interface.static_ip_range_low

        allocation = node.get_primary_mac().claim_static_ips(
            requested_address=requested_ip, update_host_maps=False)

        self.assertThat(allocation, HasLength(1))
        [sip] = allocation
        self.assertEqual(IPAddress(requested_ip), IPAddress(sip.ip))

    def test__allocates_only_IPv6_if_IPv6_address_requested(self):
        node = make_node_attached_to_cluster_interfaces()
        ipv6_interface = find_cluster_interface(node.nodegroup, 6)
        requested_ip = ipv6_interface.static_ip_range_low

        allocation = node.get_primary_mac().claim_static_ips(
            requested_address=requested_ip, update_host_maps=False)

        self.assertThat(allocation, HasLength(1))
        [sip] = allocation
        self.assertEqual(IPAddress(requested_ip), IPAddress(sip.ip))

    def test__links_static_ip_to_user_if_passed(self):
        cluster = factory.make_NodeGroup()
        cluster_interface = factory.make_NodeGroupInterface(cluster)
        mac_address = factory.make_MACAddress(
            cluster_interface=cluster_interface)
        user = factory.make_User()
        [sip] = mac_address.claim_static_ips(
            user=user, alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            update_host_maps=False)
        self.assertEqual(sip.user, user)


class TestGetClusterInterfaces(MAASServerTestCase):
    """Tests for `MACAddress.get_cluster_interfaces`."""

    def test__returns_nothing_if_none_known(self):
        self.assertItemsEqual(
            [],
            factory.make_MACAddress_with_Node().get_cluster_interfaces())

    def test__returns_cluster_interface_if_known(self):
        cluster = factory.make_NodeGroup()
        cluster_interface = factory.make_NodeGroupInterface(cluster)
        mac = factory.make_MACAddress_with_Node(
            cluster_interface=cluster_interface)
        self.assertItemsEqual(
            [cluster_interface],
            mac.get_cluster_interfaces())

    def test__includes_IPv6_cluster_interface(self):
        # If the MAC is directly attached to an IPv4 cluster interface, but
        # there's also an IPv6 cluster interface on the same network segment,
        # both those cluster interfaces are included.
        # XXX jtv 2014-08-18 bug=1358130: The way we look up the IPv6 interface
        # from the IPv4 one is set to change.  It may affect this test.
        cluster = factory.make_NodeGroup()
        network_interface = factory.make_name('eth', sep='')
        ipv4_interface = factory.make_NodeGroupInterface(
            nodegroup=cluster, network=factory.make_ipv4_network(),
            interface=network_interface)
        ipv6_interface = factory.make_NodeGroupInterface(
            nodegroup=cluster, network=factory.make_ipv6_network(),
            interface=network_interface)
        mac = factory.make_MACAddress_with_Node(
            cluster_interface=ipv4_interface)
        self.assertItemsEqual(
            [ipv4_interface, ipv6_interface],
            mac.get_cluster_interfaces())

    def test__ignores_other_cluster_interfaces(self):
        cluster = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(
            nodegroup=cluster, network=factory.make_ipv4_network())
        factory.make_NodeGroupInterface(
            nodegroup=cluster, network=factory.make_ipv6_network())
        node = factory.make_Node(nodegroup=cluster)
        self.assertItemsEqual(
            [],
            factory.make_MACAddress(node=node).get_cluster_interfaces())

    def test__ignores_other_clusters(self):
        my_cluster = factory.make_NodeGroup()
        unrelated_cluster = factory.make_NodeGroup()
        my_interface = factory.make_NodeGroupInterface(
            my_cluster, network=factory.make_ipv4_network(),
            name='eth0', interface='eth0')
        factory.make_NodeGroupInterface(
            unrelated_cluster, network=factory.make_ipv6_network(),
            name='eth0', interface='eth0')
        my_node = factory.make_Node(nodegroup=my_cluster)
        my_mac = factory.make_MACAddress_with_Node(
            node=my_node, cluster_interface=my_interface)
        self.assertItemsEqual([my_interface], my_mac.get_cluster_interfaces())


def make_cluster_with_macs_and_leases(use_static_range=False):
    cluster = factory.make_NodeGroup()
    mac_addresses = {
        factory.make_MACAddress_with_Node():
        factory.make_NodeGroupInterface(nodegroup=cluster)
        for _ in range(4)
        }
    leases = {
        get_random_ip_from_interface_range(interface, use_static_range): (
            mac_address.mac_address)
        for mac_address, interface in mac_addresses.viewitems()
    }
    return cluster, mac_addresses, leases


def make_cluster_with_mac_and_node_and_ip(use_static_range=False):
    cluster = factory.make_NodeGroup()
    mac_address = factory.make_MACAddress_with_Node()
    interface = factory.make_NodeGroupInterface(nodegroup=cluster)
    ip = get_random_ip_from_interface_range(interface, use_static_range)
    return cluster, interface, mac_address, ip


class TestUpdateMacClusterInterfaces(MAASServerTestCase):
    """Tests for `update_mac_cluster_interfaces`()."""

    def test_updates_mac_cluster_interfaces(self):
        cluster, interface, mac_address, ip = (
            make_cluster_with_mac_and_node_and_ip())
        update_mac_cluster_interfaces(ip, mac_address.mac_address, cluster)
        mac_address = reload_object(mac_address)
        self.assertEqual(interface, mac_address.cluster_interface)

    def test_considers_static_range_when_updating_interfaces(self):
        cluster, mac_addresses, leases = (
            make_cluster_with_macs_and_leases(use_static_range=True))
        cluster, interface, mac_address, ip = (
            make_cluster_with_mac_and_node_and_ip(use_static_range=True))
        update_mac_cluster_interfaces(ip, mac_address.mac_address, cluster)
        mac_address = reload_object(mac_address)
        self.assertEqual(interface, mac_address.cluster_interface)

    def test_updates_network_relations(self):
        # update_mac_cluster_interfaces should also associate the mac
        # with the network on which it resides.
        cluster, mac_addresses, leases = (
            make_cluster_with_macs_and_leases())
        cluster, interface, mac_address, ip = (
            make_cluster_with_mac_and_node_and_ip())
        net = create_Network_from_NodeGroupInterface(interface)
        update_mac_cluster_interfaces(ip, mac_address.mac_address, cluster)
        [observed_macddress] = net.macaddress_set.all()
        self.expectThat(mac_address, Equals(observed_macddress))
        self.expectThat(
            net, MatchesStructure.byEquality(
                default_gateway=interface.router_ip,
                netmask=interface.subnet_mask,
            ))

    def test_does_not_overwrite_network_with_same_name(self):
        cluster = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(nodegroup=cluster)
        net1 = create_Network_from_NodeGroupInterface(ngi)

        other_ngi = factory.make_NodeGroupInterface(nodegroup=cluster)
        other_ngi.interface = ngi.interface
        net2 = create_Network_from_NodeGroupInterface(ngi)
        self.assertEqual(None, net2)
        self.assertItemsEqual([net1], Network.objects.all())

    def test_ignores_mac_not_attached_to_cluster(self):
        cluster = factory.make_NodeGroup()
        mac_address = factory.make_MACAddress_with_Node()
        ip = factory.make_ipv4_address()
        update_mac_cluster_interfaces(ip, mac_address.mac_address, cluster)
        mac_address = MACAddress.objects.get(
            id=mac_address.id)
        self.assertIsNone(mac_address.cluster_interface)

    def test_ignores_unknown_macs(self):
        cluster = factory.make_NodeGroup()
        mac_address = factory.make_mac_address()
        ip = factory.make_ipv4_address()
        # This is a test to show that update_mac_cluster_interfaces()
        # doesn't raise an Http404 when it comes across something it
        # doesn't know, hence the lack of meaningful assertions.
        update_mac_cluster_interfaces(ip, mac_address, cluster)
        self.assertFalse(
            MACAddress.objects.filter(mac_address=mac_address).exists())

    def test_ignores_unconfigured_interfaces(self):
        cluster = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(
            nodegroup=cluster, subnet_mask='', broadcast_ip='',
            static_ip_range_low='', static_ip_range_high='',
            ip_range_low='', ip_range_high='', router_ip='',
            ip=factory.make_ipv4_address(),
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        mac_address = factory.make_mac_address()
        ip = factory.make_ipv4_address()
        self.assertIsNone(
            update_mac_cluster_interfaces(ip, mac_address, cluster))
        # The real test is that update_mac_cluster_interfaces() doesn't
        # stacktrace because of the unconfigured interface (see bug
        # 1332596).


class TestUpdateMacsClusterInterfaces(MAASServerTestCase):
    """Tests for `update_macs_cluster_interfaces`()."""

    def test_updates_macs_cluster_interfaces(self):
        cluster, mac_addresses, leases = (
            make_cluster_with_macs_and_leases())
        update_macs_cluster_interfaces(leases, cluster)
        interfaces = [inter for _, inter in mac_addresses.items()]
        linked_interfaces = (
            [reload_object(mac).cluster_interface
             for mac, _ in mac_addresses.items()])
        self.assertEquals(interfaces, linked_interfaces)

    def test_ignores_unknown_macs(self):
        mac_address = factory.make_mac_address()
        ip = factory.make_ipv4_address()
        cluster, mac_addresses, leases = (
            make_cluster_with_macs_and_leases())
        leases[ip] = mac_address
        update_macs_cluster_interfaces(leases, cluster)
        interfaces = [inter for _, inter in mac_addresses.items()]
        linked_interfaces = (
            [reload_object(mac).cluster_interface
             for mac, _ in mac_addresses.items()])
        self.assertEquals(interfaces, linked_interfaces)


class TestSetStaticIP(MAASServerTestCase):
    """Tests for `MACAddress.set_static_ip`."""

    def test_sets_unknown_sticky_ip(self):
        mac = factory.make_MACAddress_with_Node()
        user = factory.make_User()
        ip_address = factory.make_ip_address()
        static_ip = mac.set_static_ip(ip_address, user, update_host_maps=False)

        matcher = MatchesStructure(
            id=Not(Is(None)),  # IP persisted in the DB.
            ip=Equals(ip_address),
            user=Equals(user),
            alloc_type=Equals(IPADDRESS_TYPE.STICKY),
        )
        self.assertThat(static_ip, matcher)

    def test_sets_sticky_ip_from_connected_static_range(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = factory.make_Node(mac=True, nodegroup=nodegroup)
        mac = node.macaddress_set.all()[0]
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        mac.cluster_interface = ngi
        mac.save()

        user = factory.make_User()
        # Pick an address from the static range.
        static_range = IPRange(
            ngi.static_ip_range_low, ngi.static_ip_range_high)
        ip_address = factory.pick_ip_in_network(static_range)
        static_ip = mac.set_static_ip(ip_address, user, update_host_maps=False)

        matcher = MatchesStructure(
            id=Not(Is(None)),  # IP persisted in the DB.
            ip=Equals(ip_address),
            user=Equals(user),
            alloc_type=Equals(IPADDRESS_TYPE.STICKY),
        )
        self.assertThat(static_ip, matcher)

    def test_rejects_ip_from_dynamic_range(self):
        node = factory.make_Node(mac=True)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup=nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)

        user = factory.make_User()
        mac = node.macaddress_set.all()[0]
        # Pick an address from the dynamic range.
        dynamic_range = IPRange(ngi.ip_range_low, ngi.ip_range_high)
        ip_address = factory.pick_ip_in_network(dynamic_range)
        with ExpectedException(StaticIPAddressForbidden):
            mac.set_static_ip(ip_address, user, update_host_maps=False)

    def test_rejects_ip_if_ip_not_part_of_connected_network(self):
        node = factory.make_Node(mac=True)
        mac = node.macaddress_set.all()[0]
        network = factory.make_ipv4_network()
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED, network=network)
        ngi = factory.make_NodeGroupInterface(
            nodegroup=nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        mac.cluster_interface = ngi
        mac.save()

        user = factory.make_User()
        # Pick an address from a different network.
        other_network = factory.make_ipv4_network(disjoint_from=[network])
        ip_address = factory.pick_ip_in_network(other_network)
        with ExpectedException(StaticIPAddressConflict):
            mac.set_static_ip(ip_address, user, update_host_maps=False)

    def test_returns_existing_allocation_if_it_exists(self):
        mac = factory.make_MACAddress_with_Node()
        user = factory.make_User()
        ip_address = factory.make_ip_address()
        static_ip = mac.set_static_ip(ip_address, user, update_host_maps=False)

        static_ip2 = mac.set_static_ip(
            ip_address, user, update_host_maps=False)

        self.assertEquals(static_ip.id, static_ip2.id)

    def test_rejects_ip_if_other_sticky_allocation_already_exists(self):
        other_mac = factory.make_MACAddress_with_Node()
        user = factory.make_User()
        ip_address = factory.make_ip_address()
        other_mac.set_static_ip(ip_address, user, update_host_maps=False)

        mac = factory.make_MACAddress_with_Node()
        with ExpectedException(StaticIPAddressUnavailable):
            mac.set_static_ip(ip_address, user, update_host_maps=False)

    def test_rejects_ip_if_allocation_with_other_type_already_exists(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        user = factory.make_User()
        node = factory.make_Node(mac=True, nodegroup=nodegroup)
        mac = node.macaddress_set.all()[0]
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        mac.cluster_interface = ngi
        mac.save()
        # Create an AUTO IP allocation.
        static_ip = mac.claim_static_ips(update_host_maps=False)[0]

        with ExpectedException(StaticIPAddressUnavailable):
            mac.set_static_ip(static_ip.ip, user, update_host_maps=False)
