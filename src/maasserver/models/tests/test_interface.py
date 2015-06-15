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


from maasserver.enum import INTERFACE_TYPE
from maasserver.models.interface import (
    BondInterface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure


class InterfaceTest(MAASServerTestCase):

    def test_creates_interface(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        self.assertThat(interface, MatchesStructure.byEquality(
            mac=mac, name=name, type=INTERFACE_TYPE.PHYSICAL))

    def test_unicode_representation_contains_essential_data(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        self.assertIn(mac.mac_address.get_raw(), unicode(interface))
        self.assertIn(name, unicode(interface))


class PhysicalInterfaceTest(MAASServerTestCase):

    def test_manager_returns_physical_interfaces(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertItemsEqual(
            [parent], PhysicalInterface.objects.all())

    def test_get_node_returns_parent_node(self):
        mac = factory.make_MACAddress_with_Node()
        interface = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        self.assertEqual(mac.node, interface.get_node())


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
