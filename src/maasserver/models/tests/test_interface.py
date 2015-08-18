# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Interface model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.db import IntegrityError
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.models import (
    Fabric,
    MACAddress,
    Space,
    Subnet,
    VLAN,
)
from maasserver.models.interface import (
    BondInterface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPNetwork
from testtools.matchers import (
    Contains,
    MatchesStructure,
    Not,
)


class InterfaceTest(MAASServerTestCase):

    def test_creates_interface(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        self.assertThat(interface, MatchesStructure.byEquality(
            mac=mac, name=name, type=INTERFACE_TYPE.PHYSICAL))

    def test_cannot_create_multiple_with_the_same_mac_and_name(self):
        name = factory.make_name("eth")
        mac = factory.make_MACAddress()
        PhysicalInterface(mac=mac, name=name).save()
        self.assertRaises(
            IntegrityError, PhysicalInterface(mac=mac, name=name).save)

    def test_unicode_representation_contains_essential_data(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        self.assertIn(mac.mac_address.get_raw(), unicode(interface))
        self.assertIn(name, unicode(interface))

    def test_removed_if_underlying_mac_gets_removed(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        mac.delete()
        self.assertItemsEqual(
            [], PhysicalInterface.objects.filter(id=interface.id))


class PhysicalInterfaceTest(MAASServerTestCase):

    def test_manager_returns_physical_interfaces(self):
        mac = factory.make_MACAddress_with_Node(iftype=None)
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertItemsEqual(
            [parent], PhysicalInterface.objects.all())

    def test_get_node_returns_parent_node(self):
        mac = factory.make_MACAddress_with_Node(iftype=None)
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        self.assertEqual(mac.node, interface.get_node())

    def test_leaves_underlying_mac_intact_when_removed(self):
        mac = factory.make_MACAddress_with_Node(iftype=None)
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        interface.delete()
        self.assertItemsEqual(
            [mac], MACAddress.objects.filter(id=mac.id))


class VLANInterfaceTest(MAASServerTestCase):

    def test_vlan_has_generated_name(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertEqual('vlan%d' % vlan.vid, interface.name)

    def test_generated_name_gets_update_if_vlan_id_changes(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        new_vlan = factory.make_VLAN()
        interface.vlan = new_vlan
        interface.save()
        self.assertEqual('vlan%d' % new_vlan.vid, interface.name)

    def test_manager_returns_vlan_interfaces(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertItemsEqual(
            [interface], VLANInterface.objects.all())

    def test_get_node_returns_parent_node(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertEqual(mac.node, interface.get_node())

    def test_removed_if_underlying_interface_gets_removed(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        mac.delete()
        self.assertItemsEqual(
            [], VLANInterface.objects.filter(id=interface.id))


class BondInterfaceTest(MAASServerTestCase):

    def test_manager_returns_bond_interfaces(self):
        mac1 = factory.make_MACAddress_with_Node()
        mac2 = factory.make_MACAddress_with_Node(node=mac1.node)
        parent1 = factory.make_Interface(
            mac=mac1, type=INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            mac=mac2, type=INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            type=INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        self.assertItemsEqual(
            [interface], BondInterface.objects.all())

    def test_get_node_returns_first_parent_node(self):
        mac1 = factory.make_MACAddress_with_Node()
        mac2 = factory.make_MACAddress_with_Node(node=mac1.node)
        parent1 = factory.make_Interface(
            mac=mac1, type=INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            mac=mac2, type=INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            type=INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        self.assertItemsEqual(
            [interface], BondInterface.objects.all())
        self.assertEqual(mac1.node, interface.get_node())

    def test_removed_if_underlying_interface_gets_removed(self):
        mac1 = factory.make_MACAddress_with_Node()
        mac2 = factory.make_MACAddress_with_Node(node=mac1.node)
        parent1 = factory.make_Interface(
            mac=mac1, type=INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            mac=mac2, type=INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            type=INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        mac1.delete()
        self.assertItemsEqual(
            [], BondInterface.objects.filter(id=interface.id))


class UpdateIpAddressesTest(MAASServerTestCase):

    def test__creates_missing_subnet(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        address = unicode(network.ip)
        interface.update_ip_addresses([cidr])

        default_fabric = Fabric.objects.get_default_fabric()
        default_space = Space.objects.get_default_space()
        subnets = Subnet.objects.filter(
            cidr=unicode(network.cidr), vlan__fabric=default_fabric,
            space=default_space)
        self.assertEqual(1, len(subnets))
        self.assertEqual(1, interface.ip_addresses.count())
        self.assertThat(
            interface.ip_addresses.first(),
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnets[0],
                ip=address))

    def test__creates_dhcp_ip_addresses(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        num_connections = 3
        cidr_list = [
            unicode(factory.make_ip4_or_6_network()) for _
            in range(num_connections)
            ]
        subnet_list = [
            factory.make_Subnet(cidr=cidr, vlan=vlan) for cidr in cidr_list]

        interface.update_ip_addresses(cidr_list)

        self.assertEqual(num_connections, interface.ip_addresses.count())
        for i in range(num_connections):
            ip = interface.ip_addresses.all()[i]
            self.assertThat(ip, MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet_list[i],
                ip=unicode(IPNetwork(cidr_list[i]).ip)))

    def test__creates_link_with_empty_ip_if_conflicting_static_ip(self):
        mac = factory.make_MACAddress_with_Node()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        address = unicode(network.ip)
        vlan = VLAN.objects.get_default_vlan()
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        other_mac = factory.make_MACAddress_with_Node()
        other_interface = factory.make_Interface(
            mac=other_mac, type=INTERFACE_TYPE.PHYSICAL)
        ip = factory.make_StaticIPAddress(
            subnet=subnet, ip=address,
            alloc_type=IPADDRESS_TYPE.STICKY)
        other_interface.ip_addresses.add(ip)
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)

        interface.update_ip_addresses([cidr])

        self.assertEqual(1, interface.ip_addresses.count())
        self.assertThat(
            interface.ip_addresses.first(),
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet,
                ip=None))

    def test__creates_link_if_conflicting_dhcp_ip(self):
        mac = factory.make_MACAddress_with_Node()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        address = unicode(network.ip)
        vlan = VLAN.objects.get_default_vlan()
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        other_mac = factory.make_MACAddress_with_Node()
        other_interface = factory.make_Interface(
            mac=other_mac, type=INTERFACE_TYPE.PHYSICAL)
        ip = factory.make_StaticIPAddress(
            subnet=subnet, ip=address,
            alloc_type=IPADDRESS_TYPE.DHCP)
        other_interface.ip_addresses.add(ip)
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)

        interface.update_ip_addresses([cidr])

        self.assertEqual(1, interface.ip_addresses.count())
        self.assertThat(
            interface.ip_addresses.first(),
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet,
                ip=address))
        self.assertIsNone(reload_object(ip).ip)

    def test__updates_ip_of_dhcp_address(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        ip = factory.make_StaticIPAddress(
            subnet=subnet, ip=factory.pick_ip_in_network(network),
            alloc_type=IPADDRESS_TYPE.DHCP)
        interface.ip_addresses.add(ip)

        interface.update_ip_addresses([cidr])

        self.assertItemsEqual([ip], interface.ip_addresses.all())
        self.assertEqual(unicode(network.ip), reload_object(ip).ip)

    def test__updates_legacy_static_ip_addresses(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        network = factory.make_ip4_or_6_network()
        address = unicode(network.ip)
        cidr = unicode(network)
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        ip = factory.make_StaticIPAddress(
            subnet=None, ip=address, mac=mac,
            alloc_type=IPADDRESS_TYPE.STICKY)

        interface.update_ip_addresses([cidr])

        self.assertItemsEqual([ip], interface.ip_addresses.all())
        self.assertEqual(subnet, reload_object(ip).subnet)

    def test__updates_linked_static_ip_addresses(self):
        # New-style static IP addresses (i.e. static IP addresses linked
        # to a subnet) are picked up by `connect()`.
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        network = factory.make_ip4_or_6_network()
        address = unicode(network.ip)
        cidr = unicode(network)
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        ip = factory.make_StaticIPAddress(
            subnet=subnet, ip=address, alloc_type=IPADDRESS_TYPE.STICKY)
        interface.ip_addresses.add(ip)

        interface.update_ip_addresses([cidr])

        self.assertItemsEqual([ip], interface.ip_addresses.all())
        self.assertEqual(subnet, reload_object(ip).subnet)

    def test__removes_obsolete_links(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        old_subnet = factory.make_Subnet()
        old_ip = factory.make_StaticIPAddress(
            subnet=old_subnet, ip=factory.pick_ip_in_network(network),
            alloc_type=IPADDRESS_TYPE.DHCP)
        interface.ip_addresses.add(old_ip)

        interface.update_ip_addresses([cidr])

        self.assertThat(interface.ip_addresses.all(), Not(Contains(old_ip)))
        self.assertEqual(1, interface.ip_addresses.count())
        self.assertThat(
            interface.ip_addresses.first(),
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet,
                ip=unicode(IPNetwork(cidr).ip)))
