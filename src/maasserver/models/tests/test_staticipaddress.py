# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`StaticIPAddress` tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.core.exceptions import ValidationError
from maasserver.enum import IPADDRESS_TYPE
from maasserver.exceptions import StaticIPAddressExhaustion
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from netaddr import (
    IPAddress,
    IPRange,
    )


class StaticIPAddressManagerTest(MAASServerTestCase):

    def test_allocate_new_returns_ip_in_correct_range(self):
        low, high = factory.make_ip_range()
        ipaddress = StaticIPAddress.objects.allocate_new(low, high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        iprange = IPRange(low, high)
        self.assertIn(IPAddress(ipaddress.ip), iprange)

    def test_allocate_new_raises_when_addresses_exhausted(self):
        low = high = "192.168.230.1"
        StaticIPAddress.objects.allocate_new(low, high)
        self.assertRaises(
            StaticIPAddressExhaustion,
            StaticIPAddress.objects.allocate_new, low, high)

    def test_allocate_new_sets_user(self):
        low, high = factory.make_ip_range()
        user = factory.make_user()
        ipaddress = StaticIPAddress.objects.allocate_new(
            low, high, alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user)
        self.assertEqual(user, ipaddress.user)

    def test_allocate_new_with_user_disallows_wrong_alloc_types(self):
        low, high = factory.make_ip_range()
        user = factory.make_user()
        alloc_type = factory.getRandomEnum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        self.assertRaises(
            AssertionError, StaticIPAddress.objects.allocate_new, low, high,
            user=user, alloc_type=alloc_type)

    def test_allocate_new_with_reserved_type_requires_a_user(self):
        low, high = factory.make_ip_range()                 
        self.assertRaises(                                  
            AssertionError, StaticIPAddress.objects.allocate_new, low, high,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED)

    def test_deallocate_by_node_removes_addresses(self):
        node = factory.make_node()
        [mac1, mac2] = [
            factory.make_mac_address(node=node) for _ in range(2)]
        factory.make_staticipaddress(mac=mac1)
        factory.make_staticipaddress(mac=mac2)
        StaticIPAddress.objects.deallocate_by_node(node)
        # Check the DB is cleared.
        self.assertEqual([], list(StaticIPAddress.objects.all()))
        # Check the link table is cleared.
        self.assertEqual([], list(node.static_ip_addresses()))

    def test_deallocate_by_node_returns_deallocated_ips(self):
        node = factory.make_node()
        [mac1, mac2] = [
            factory.make_mac_address(node=node) for _ in range(2)]
        ip1 = factory.make_staticipaddress(mac=mac1)
        ip2 = factory.make_staticipaddress(mac=mac2)
        observed = StaticIPAddress.objects.deallocate_by_node(node)
        self.assertItemsEqual(
            [ip1.ip.format(), ip2.ip.format()],
            observed
            )

    def test_deallocate_by_node_ignores_other_nodes(self):
        node1 = factory.make_node()
        mac1 = factory.make_mac_address(node=node1)
        factory.make_staticipaddress(mac=mac1)
        node2 = factory.make_node()
        mac2 = factory.make_mac_address(node=node2)
        ip2 = factory.make_staticipaddress(mac=mac2)

        StaticIPAddress.objects.deallocate_by_node(node1)
        self.assertItemsEqual([ip2.ip], node2.static_ip_addresses())

    def test_deallocate_only_deletes_auto_types(self):
        node = factory.make_node()
        mac = factory.make_mac_address(node=node)
        alloc_types = map_enum(IPADDRESS_TYPE).values()
        for alloc_type in alloc_types:
            factory.make_staticipaddress(mac=mac, alloc_type=alloc_type)

        StaticIPAddress.objects.deallocate_by_node(node)
        types_without_auto = set(alloc_types)
        types_without_auto.discard(IPADDRESS_TYPE.AUTO)
        self.assertItemsEqual(
            types_without_auto,
            [ip.alloc_type for ip in StaticIPAddress.objects.all()])

    def test_delete_by_node_removes_addresses(self):
        node = factory.make_node()
        [mac1, mac2] = [
            factory.make_mac_address(node=node) for _ in range(2)]
        factory.make_staticipaddress(mac=mac1)
        factory.make_staticipaddress(mac=mac2)
        StaticIPAddress.objects.delete_by_node(node)
        # Check the DB is cleared.
        self.assertEqual([], list(StaticIPAddress.objects.all()))
        # Check the link table is cleared.
        self.assertEqual([], list(node.static_ip_addresses()))

    def test_delete_by_node_returns_deallocated_ips(self):
        node = factory.make_node()
        [mac1, mac2] = [
            factory.make_mac_address(node=node) for _ in range(2)]
        ip1 = factory.make_staticipaddress(mac=mac1)
        ip2 = factory.make_staticipaddress(mac=mac2)
        observed = StaticIPAddress.objects.delete_by_node(node)
        self.assertItemsEqual(
            [ip1.ip.format(), ip2.ip.format()],
            observed
            )

    def test_delete_by_node_ignores_other_nodes(self):
        node1 = factory.make_node()
        mac1 = factory.make_mac_address(node=node1)
        factory.make_staticipaddress(mac=mac1)
        other_node = factory.make_node()
        other_mac = factory.make_mac_address(node=other_node)
        other_ip = factory.make_staticipaddress(mac=other_mac)

        StaticIPAddress.objects.delete_by_node(node1)
        self.assertItemsEqual([other_ip.ip], other_node.static_ip_addresses())

    def test_delete_by_node_deletes_all_types(self):
        node = factory.make_node()
        mac = factory.make_mac_address(node=node)
        alloc_types = map_enum(IPADDRESS_TYPE).values()
        for alloc_type in alloc_types:
            factory.make_staticipaddress(mac=mac, alloc_type=alloc_type)

        StaticIPAddress.objects.delete_by_node(node)
        self.assertItemsEqual([], StaticIPAddress.objects.all())


class StaticIPAddressManagerMappingTest(MAASServerTestCase):
    """Tests for get_hostname_ip_mapping()."""

    def test_get_hostname_ip_mapping_returns_mapping(self):
        nodegroup = factory.make_node_group()
        expected_mapping = {}
        for i in range(3):
            node = factory.make_node_with_mac_attached_to_nodegroupinterface(
                nodegroup=nodegroup)
            staticip = factory.make_staticipaddress(mac=node.get_primary_mac())
            expected_mapping[node.hostname] = staticip.ip
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup)
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_strips_out_domain(self):
        nodegroup = factory.make_node_group()
        hostname = factory.make_name('hostname')
        domain = factory.make_name('domain')
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            nodegroup=nodegroup, hostname="%s.%s" % (hostname, domain))
        staticip = factory.make_staticipaddress(mac=node.get_primary_mac())
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup)
        self.assertEqual({hostname: staticip.ip}, mapping)

    def test_get_hostname_ip_mapping_picks_mac_with_static_address(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            hostname=factory.make_name('host'))
        second_mac = factory.make_mac_address(node=node)
        staticip = factory.make_staticipaddress(mac=second_mac)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertEqual({node.hostname: staticip.ip}, mapping)

    def test_get_hostname_ip_mapping_considers_given_nodegroup(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            nodegroup=nodegroup)
        factory.make_staticipaddress(mac=node.get_primary_mac())
        another_nodegroup = factory.make_node_group()
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            another_nodegroup)
        self.assertEqual({}, mapping)

    def test_get_hostname_ip_mapping_picks_oldest_mac_with_static_ip(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            hostname=factory.make_name('host'))
        newer_mac = factory.make_mac_address(node=node)
        factory.make_staticipaddress(mac=newer_mac)
        ip_for_older_mac = factory.make_staticipaddress(
            mac=node.get_primary_mac())
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            node.nodegroup)
        self.assertEqual({node.hostname: ip_for_older_mac.ip}, mapping)


class StaticIPAddressTest(MAASServerTestCase):

    def test_repr_with_valid_type(self):
        actual = "%s" % factory.make_staticipaddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEqual("<StaticIPAddress: <10.0.0.1:type=AUTO>>", actual)

    def test_repr_with_invalid_type(self):
        actual = "%s" % factory.make_staticipaddress(
            ip="10.0.0.1", alloc_type=99999)
        self.assertEqual("<StaticIPAddress: <10.0.0.1:type=99999>>", actual)

    def test_stores_to_database(self):
        ipaddress = factory.make_staticipaddress()
        self.assertEqual([ipaddress], list(StaticIPAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        ip = StaticIPAddress(ip='256.0.0.0.0')
        self.assertRaises(ValidationError, ip.full_clean)

    def test_deallocate_removes_object(self):
        ipaddress = factory.make_staticipaddress()
        ipaddress.deallocate()
        self.assertEqual([], list(StaticIPAddress.objects.all()))

    def test_deallocate_ignores_other_objects(self):
        ipaddress = factory.make_staticipaddress()
        ipaddress2 = factory.make_staticipaddress()
        ipaddress.deallocate()
        self.assertEqual([ipaddress2], list(StaticIPAddress.objects.all()))
