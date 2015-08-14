# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`StaticIPAddress` tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)
from testtools.matchers import HasLength


str = None

__metaclass__ = type
__all__ = []


from django.core.exceptions import ValidationError
from maasserver import locks
from maasserver.enum import IPADDRESS_TYPE
from maasserver.exceptions import (
    StaticIPAddressExhaustion,
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maasserver.utils.orm import is_serialization_failure
from mock import sentinel
from netaddr import (
    IPAddress,
    IPRange,
)
from provisioningserver.utils.enum import map_enum
from random import randint
from django.db import transaction


class TestStaticIPAddressManager(MAASServerTestCase):

    def make_ip_ranges(self, network=None, nodegroup=None):
        if not nodegroup:
            nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(
            nodegroup, network=network)
        return (
            interface.network,
            interface.static_ip_range_low,
            interface.static_ip_range_high,
            interface.ip_range_low,
            interface.ip_range_low,
        )

    def test_allocate_new_returns_ip_in_correct_range(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        iprange = IPRange(static_low, static_high)
        self.assertIn(IPAddress(ipaddress.ip), iprange)

    def test_allocate_new_allocates_IPv6_address(self):
        network = factory.make_ipv6_network()
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges(network))
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertIn(
            IPAddress(ipaddress.ip), IPRange(static_low, static_high))

    def test_allocate_new_sets_user(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        user = factory.make_User()
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user)
        self.assertEqual(user, ipaddress.user)

    def test_allocate_new_with_user_disallows_wrong_alloc_types(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        user = factory.make_User()
        alloc_type = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        self.assertRaises(
            AssertionError, StaticIPAddress.objects.allocate_new, network,
            static_low, static_high, dynamic_low, dynamic_high,
            user=user, alloc_type=alloc_type)

    def test_allocate_new_with_reserved_type_requires_a_user(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        self.assertRaises(
            AssertionError, StaticIPAddress.objects.allocate_new, network,
            static_low, static_high, dynamic_low, dynamic_high,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED)

    def test_allocate_new_compares_by_IP_not_alphabetically(self):
        # Django has a bug that casts IP addresses with HOST(), which
        # results in alphabetical comparisons of strings instead of IP
        # addresses.  See https://bugs.launchpad.net/maas/+bug/1338452
        network = "10.0.0.0/8"
        static_low = "10.0.0.98"
        static_high = "10.0.0.100"
        dynamic_low = "10.0.0.101"
        dynamic_high = "10.0.0.105"
        factory.make_StaticIPAddress("10.0.0.99")
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertEqual(ipaddress.ip, "10.0.0.98")

    def test_allocate_new_returns_requested_IP_if_available(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = unicode(IPAddress(static_low) + 1)
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED]),
            requested_address=requested_address)
        self.assertEqual(requested_address.format(), ipaddress.ip)

    def test_allocate_new_raises_when_requested_IP_unavailable(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])).ip
        self.assertRaises(
            StaticIPAddressUnavailable, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high,
            requested_address=requested_address)

    def test_allocate_new_raises_serialization_error_if_ip_taken(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        # Simulate a "IP already taken" error.
        mock_attempt_allocation = self.patch(
            StaticIPAddress.objects, '_attempt_allocation')
        mock_attempt_allocation.side_effect = StaticIPAddressUnavailable()

        error = self.assertRaises(
            Exception, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertTrue(is_serialization_failure(error))

    def test_allocate_new_does_not_use_lock_for_requested_ip(self):
        # When requesting a specific IP address, there's no need to
        # acquire the lock.
        lock = self.patch(locks, 'staticip_acquire')
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = unicode(IPAddress(static_low) + 1)
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high,
            requested_address=requested_address)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertThat(lock.__enter__, MockNotCalled())

    def test_allocate_new_raises_when_requested_IP_out_of_network(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        other_network = factory.make_ipv4_network(but_not=network)
        requested_address = factory.pick_ip_in_network(other_network)
        e = self.assertRaises(
            StaticIPAddressOutOfRange, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED]),
            requested_address=requested_address)
        self.assertEqual(
            "%s is not inside the network %s" % (
                requested_address, network),
            e.message)

    def test_allocate_new_raises_when_requested_IP_in_dynamic_range(self):
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        requested_address = dynamic_low
        e = self.assertRaises(
            StaticIPAddressOutOfRange, StaticIPAddress.objects.allocate_new,
            network, static_low, static_high, dynamic_low, dynamic_high,
            factory.pick_enum(
                IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED]),
            requested_address=requested_address)
        self.assertEqual(
            "%s is inside the dynamic range %s to %s" % (
                requested_address, dynamic_low, dynamic_high),
            e.message)

    def test_allocate_new_raises_when_alloc_type_is_None(self):
        error = self.assertRaises(
            ValueError, StaticIPAddress.objects.allocate_new,
            sentinel.network, sentinel.static_range_low,
            sentinel.static_range_low, sentinel.dynamic_range_low,
            sentinel.dynamic_range_high, alloc_type=None)
        self.assertEqual(
            "IP address type None is not a member of IPADDRESS_TYPE.",
            unicode(error))

    def test_allocate_new_raises_when_alloc_type_is_invalid(self):
        error = self.assertRaises(
            ValueError, StaticIPAddress.objects.allocate_new,
            sentinel.network, sentinel.static_range_low,
            sentinel.static_range_low, sentinel.dynamic_range_low,
            sentinel.dynamic_range_high, alloc_type=12345)
        self.assertEqual(
            "IP address type 12345 is not a member of IPADDRESS_TYPE.",
            unicode(error))

    def test_allocate_new_uses_staticip_acquire_lock(self):
        lock = self.patch(locks, 'staticip_acquire')
        network, static_low, static_high, dynamic_low, dynamic_high = (
            self.make_ip_ranges())
        ipaddress = StaticIPAddress.objects.allocate_new(
            network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertThat(lock.__enter__, MockCalledOnceWith())
        self.assertThat(
            lock.__exit__, MockCalledOnceWith(None, None, None))

    def test_deallocate_by_node_removes_addresses(self):
        node = factory.make_Node()
        [mac1, mac2] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        factory.make_StaticIPAddress(mac=mac1)
        factory.make_StaticIPAddress(mac=mac2)
        StaticIPAddress.objects.deallocate_by_node(node)
        # Check the DB is cleared.
        self.assertEqual([], list(StaticIPAddress.objects.all()))
        # Check the link table is cleared.
        self.assertEqual([], list(node.static_ip_addresses()))

    def test_deallocate_by_node_returns_deallocated_ips(self):
        node = factory.make_Node()
        [mac1, mac2] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        ip1 = factory.make_StaticIPAddress(mac=mac1)
        ip2 = factory.make_StaticIPAddress(mac=mac2)
        observed = StaticIPAddress.objects.deallocate_by_node(node)
        self.assertItemsEqual(
            [
                ip1.ip.format(),
                ip2.ip.format(),
                unicode(mac1.mac_address),
                unicode(mac2.mac_address),
            ],
            observed
        )

    def test_deallocate_by_node_ignores_other_nodes(self):
        node1 = factory.make_Node()
        mac1 = factory.make_MACAddress(node=node1)
        factory.make_StaticIPAddress(mac=mac1)
        node2 = factory.make_Node()
        mac2 = factory.make_MACAddress(node=node2)
        ip2 = factory.make_StaticIPAddress(mac=mac2)

        StaticIPAddress.objects.deallocate_by_node(node1)
        self.assertItemsEqual([ip2.ip], node2.static_ip_addresses())

    def test_deallocate_only_deletes_auto_types(self):
        node = factory.make_Node()
        mac = factory.make_MACAddress(node=node)
        alloc_types = map_enum(IPADDRESS_TYPE).values()
        for alloc_type in alloc_types:
            factory.make_StaticIPAddress(mac=mac, alloc_type=alloc_type)

        StaticIPAddress.objects.deallocate_by_node(node)
        types_without_auto = set(alloc_types)
        types_without_auto.discard(IPADDRESS_TYPE.AUTO)
        self.assertItemsEqual(
            types_without_auto,
            [ip.alloc_type for ip in StaticIPAddress.objects.all()])

    def test_delete_by_node_removes_addresses(self):
        node = factory.make_Node()
        [mac1, mac2] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        factory.make_StaticIPAddress(mac=mac1)
        factory.make_StaticIPAddress(mac=mac2)
        StaticIPAddress.objects.delete_by_node(node)
        # Check the DB is cleared.
        self.assertEqual([], list(StaticIPAddress.objects.all()))
        # Check the link table is cleared.
        self.assertEqual([], list(node.static_ip_addresses()))

    def test_delete_by_node_returns_deallocated_ips(self):
        node = factory.make_Node()
        [mac1, mac2] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        ip1 = factory.make_StaticIPAddress(mac=mac1)
        ip2 = factory.make_StaticIPAddress(mac=mac2)
        observed = StaticIPAddress.objects.delete_by_node(node)
        self.assertItemsEqual(
            [
                ip1.ip.format(),
                ip2.ip.format(),
                unicode(mac1.mac_address),
                unicode(mac2.mac_address),
            ],
            observed
        )

    def test_delete_by_node_ignores_other_nodes(self):
        node1 = factory.make_Node()
        mac1 = factory.make_MACAddress(node=node1)
        factory.make_StaticIPAddress(mac=mac1)
        other_node = factory.make_Node()
        other_mac = factory.make_MACAddress(node=other_node)
        other_ip = factory.make_StaticIPAddress(mac=other_mac)

        StaticIPAddress.objects.delete_by_node(node1)
        self.assertItemsEqual([other_ip.ip], other_node.static_ip_addresses())

    def test_delete_by_node_deletes_all_types(self):
        node = factory.make_Node()
        mac = factory.make_MACAddress(node=node)
        alloc_types = map_enum(IPADDRESS_TYPE).values()
        for alloc_type in alloc_types:
            factory.make_StaticIPAddress(mac=mac, alloc_type=alloc_type)

        StaticIPAddress.objects.delete_by_node(node)
        self.assertItemsEqual([], StaticIPAddress.objects.all())

    def test_update_leases_new_ip_new_mac(self):
        vlan = VLAN.objects.get_default_vlan()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            vlan=vlan
        )
        mac = node.get_primary_mac()
        ngi = mac.cluster_interface
        ipaddress = factory.make_StaticIPAddress(
            ip=ngi.ip_range_low, alloc_type=IPADDRESS_TYPE.DHCP,
            subnet=ngi.subnet, mac=mac)

        # Now that we have set the conditions, add a new lease on this subnet,
        # for a new IP and mac.
        ipaddr2 = factory.pick_ip_in_network(ngi.network, [ipaddress.ip])
        mac_addr2 = factory.make_mac_address()
        StaticIPAddress.objects.update_leases(
            node.nodegroup, {ipaddr2: mac_addr2})
        new_ips = StaticIPAddress.objects.filter(ip=ipaddr2)
        self.assertEqual(1, len(new_ips))
        # we do not create mac links for this case.
        self.assertItemsEqual([], new_ips[0].get_mac_addresses())

    def test_update_leases_drop_lease(self):
        from maasserver.models.vlan import VLAN
        vlan = VLAN.objects.get_default_vlan()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            vlan=vlan
        )
        mac = node.get_primary_mac()
        ngi = mac.cluster_interface
        factory.make_StaticIPAddress(
            ip=ngi.ip_range_low, alloc_type=IPADDRESS_TYPE.DHCP,
            subnet=ngi.subnet, mac=mac)
        # and then we can do an update_leases call for this lease
        StaticIPAddress.objects.update_leases(
            node.nodegroup, {})
        new_ips = StaticIPAddress.objects.filter(ip=ngi.ip_range_low)
        # confirm that there is no entry for the new IP
        self.assertEqual(0, len(new_ips))
        # and confirm that the old entry no longer has an IP
        self.assertEqual(None, StaticIPAddress.objects.all()[0].ip)

    def test_update_leases_new_ip_existing_mac(self):
        from maasserver.models.vlan import VLAN
        vlan = VLAN.objects.get_default_vlan()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            vlan=vlan
        )
        mac = node.get_primary_mac()
        ngi = mac.cluster_interface
        ipaddress = factory.make_StaticIPAddress(
            ip=ngi.ip_range_low, alloc_type=IPADDRESS_TYPE.DHCP,
            subnet=ngi.subnet, mac=mac)
        # and then we can do an update_leases call for this lease
        ipaddr2 = factory.pick_ip_in_network(ngi.network, [ipaddress.ip])
        StaticIPAddress.objects.update_leases(
            node.nodegroup, {ipaddr2: mac.mac_address})
        new_ips = StaticIPAddress.objects.filter(ip=ipaddr2)
        self.assertThat(new_ips, HasLength(1))
        self.assertItemsEqual([mac], new_ips[0].get_mac_addresses())

    def test_update_leases_new_ip_existing_mac_different_nodegroup(self):
        vlan = VLAN.objects.get_default_vlan()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            vlan=vlan
        )
        mac = node.get_primary_mac()
        ngi = mac.cluster_interface
        ipaddress = factory.make_StaticIPAddress(
            ip=ngi.ip_range_low, alloc_type=IPADDRESS_TYPE.DHCP,
            subnet=ngi.subnet, mac=mac)
        # This is slightly overkill to get a new NodeGroup and all the
        # linkages, but makes for a more comolete test.
        node2 = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        ipaddr2 = factory.pick_ip_in_network(ngi.network, [ipaddress.ip])
        StaticIPAddress.objects.update_leases(
            node2.nodegroup, {ipaddr2: mac.mac_address})
        new_ips = StaticIPAddress.objects.filter(ip=ipaddr2)
        self.assertThat(new_ips, HasLength(1))
        # we do not create mac links for this case.
        self.assertItemsEqual([], new_ips[0].get_mac_addresses())


class TestStaticIPAddressManagerTrasactional(MAASTransactionServerTestCase):
    '''The following TestStaticIPAddressManager tests require
        MAASTransactionServerTestCase, and thus have been separated
        from the TestStaticIPAddressManager above.
    '''

    def test_allocate_new_raises_when_addresses_exhausted(self):
        network = "192.168.230.0/24"
        static_low = static_high = "192.168.230.1"
        dynamic_low = dynamic_high = "192.168.230.2"
        with transaction.atomic():
            StaticIPAddress.objects.allocate_new(
                network, static_low, static_high, dynamic_low, dynamic_high)
        with transaction.atomic():
            e = self.assertRaises(
                StaticIPAddressExhaustion,
                StaticIPAddress.objects.allocate_new,
                network, static_low, static_high, dynamic_low, dynamic_high)
        self.assertEqual(
            "No more IPs available in range %s-%s" % (static_low, static_high),
            unicode(e))


class TestStaticIPAddressManagerMapping(MAASServerTestCase):
    """Tests for get_hostname_ip_mapping()."""

    def test_get_hostname_ip_mapping_returns_mapping(self):
        nodegroup = factory.make_NodeGroup()
        expected_mapping = {}
        for _ in range(3):
            node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
                nodegroup=nodegroup)
            staticip = factory.make_StaticIPAddress(mac=node.get_primary_mac())
            expected_mapping[node.hostname] = [staticip.ip]
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup)
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_strips_out_domain(self):
        nodegroup = factory.make_NodeGroup()
        hostname = factory.make_name('hostname')
        domain = factory.make_name('domain')
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            nodegroup=nodegroup, hostname="%s.%s" % (hostname, domain))
        staticip = factory.make_StaticIPAddress(mac=node.get_primary_mac())
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup)
        self.assertEqual({hostname: [staticip.ip]}, mapping)

    def test_get_hostname_ip_mapping_picks_mac_with_static_address(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            hostname=factory.make_name('host'))
        second_mac = factory.make_MACAddress(node=node)
        staticip = factory.make_StaticIPAddress(mac=second_mac)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertEqual({node.hostname: [staticip.ip]}, mapping)

    def test_get_hostname_ip_mapping_considers_given_nodegroup(self):
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            nodegroup=nodegroup)
        factory.make_StaticIPAddress(mac=node.get_primary_mac())
        another_nodegroup = factory.make_NodeGroup()
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            another_nodegroup)
        self.assertEqual({}, mapping)

    def test_get_hostname_ip_mapping_picks_oldest_mac_with_static_ip(self):
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            hostname=factory.make_name('host'))
        newer_mac = factory.make_MACAddress(node=node)
        factory.make_StaticIPAddress(mac=newer_mac)
        ip_for_older_mac = factory.make_StaticIPAddress(
            mac=node.get_primary_mac())
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertEqual({node.hostname: [ip_for_older_mac.ip]}, mapping)

    def test_get_hostname_ip_mapping_combines_IPv4_and_IPv6_addresses(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        mac = node.get_primary_mac()
        ipv4_address = factory.make_StaticIPAddress(
            mac=mac,
            ip=factory.pick_ip_in_network(factory.make_ipv4_network()))
        ipv6_address = factory.make_StaticIPAddress(
            mac=mac,
            ip=factory.pick_ip_in_network(factory.make_ipv6_network()))
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertItemsEqual(
            [ipv4_address.ip, ipv6_address.ip],
            mapping[node.hostname])

    def test_get_hostname_ip_mapping_combines_MACs_for_same_node(self):
        # A node's preferred static IPv4 and IPv6 addresses may be on
        # different MACs.
        node = factory.make_Node(disable_ipv4=False)
        ipv4_address = factory.make_StaticIPAddress(
            mac=factory.make_MACAddress(node=node),
            ip=factory.pick_ip_in_network(factory.make_ipv4_network()))
        ipv6_address = factory.make_StaticIPAddress(
            mac=factory.make_MACAddress(node=node),
            ip=factory.pick_ip_in_network(factory.make_ipv6_network()))
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertItemsEqual(
            [ipv4_address.ip, ipv6_address.ip],
            mapping[node.hostname])

    def test_get_hostname_ip_mapping_skips_ipv4_if_disable_ipv4_set(self):
        node = factory.make_Node(mac=True, disable_ipv4=True)
        mac = node.get_primary_mac()
        factory.make_StaticIPAddress(
            mac=mac,
            ip=factory.pick_ip_in_network(factory.make_ipv4_network()))
        ipv6_address = factory.make_StaticIPAddress(
            mac=mac,
            ip=factory.pick_ip_in_network(factory.make_ipv6_network()))
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertEqual({node.hostname: [ipv6_address.ip]}, mapping)


class TestStaticIPAddress(MAASServerTestCase):

    def test_repr_with_valid_type(self):
        actual = "%s" % factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEqual("<StaticIPAddress: <10.0.0.1:type=AUTO>>", actual)

    def test_repr_with_invalid_type(self):
        actual = "%s" % factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=99999)
        self.assertEqual("<StaticIPAddress: <10.0.0.1:type=99999>>", actual)

    def test_stores_to_database(self):
        ipaddress = factory.make_StaticIPAddress()
        self.assertEqual([ipaddress], list(StaticIPAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        ip = StaticIPAddress(ip='256.0.0.0.0')
        self.assertRaises(ValidationError, ip.full_clean)

    def test_deallocate_removes_object(self):
        ipaddress = factory.make_StaticIPAddress()
        ipaddress.deallocate()
        self.assertEqual([], list(StaticIPAddress.objects.all()))

    def test_deallocate_ignores_other_objects(self):
        ipaddress = factory.make_StaticIPAddress()
        ipaddress2 = factory.make_StaticIPAddress()
        ipaddress.deallocate()
        self.assertEqual([ipaddress2], list(StaticIPAddress.objects.all()))


class TestUserReservedStaticIPAddress(MAASServerTestCase):

    def test_user_reserved_addresses_have_default_hostnames(self):
        num_ips = randint(3, 5)
        ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects._get_user_reserved_mappings()
        self.expectThat(mappings, HasLength(len(ips)))

    def test_user_reserved_addresses_included_in_get_hostname_ip_mapping(self):
        num_ips = randint(3, 5)
        nodegroup = factory.make_NodeGroup()
        ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup)
        self.expectThat(mappings, HasLength(len(ips)))

    def test_user_reserved_addresses_included_in_all_nodegroups(self):
        num_ips = randint(3, 5)
        nodegroup1 = factory.make_NodeGroup()
        nodegroup2 = factory.make_NodeGroup()
        ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED)
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup1)
        self.expectThat(mappings, HasLength(len(ips)))
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup2)
        self.expectThat(mappings, HasLength(len(ips)))
