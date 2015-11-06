# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of interface signals."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestEnableAndDisableInterface(MAASServerTestCase):

    def test__enable_interface_creates_link_up(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, enabled=False)
        interface.enabled = True
        interface.save()
        link_ip = interface.ip_addresses.get(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None)
        self.assertIsNotNone(link_ip)

    def test__enable_interface_creates_link_up_on_children(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, enabled=False)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[interface])
        interface.enabled = True
        interface.save()
        link_ip = vlan_interface.ip_addresses.get(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=None)
        self.assertIsNotNone(link_ip)

    def test__disable_interface_removes_links(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, enabled=True)
        interface.ensure_link_up()
        interface.enabled = False
        interface.save()
        self.assertItemsEqual([], interface.ip_addresses.all())

    def test__disable_interface_removes_links_on_children(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, enabled=True)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[interface])
        vlan_interface.ensure_link_up()
        interface.enabled = False
        interface.save()
        self.assertItemsEqual([], vlan_interface.ip_addresses.all())

    def test__disable_interface_doesnt_remove_links_on_enabled_children(self):
        node = factory.make_Node()
        nic0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, enabled=True)
        nic1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, enabled=True)
        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[nic0, nic1])
        bond_interface.ensure_link_up()
        nic0.enabled = False
        nic0.save()
        self.assertEquals(1, bond_interface.ip_addresses.count())


class TestMTUParams(MAASServerTestCase):

    def test__updates_children_mtu(self):
        new_mtu = random.randint(800, 2000)
        physical_interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan1_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[physical_interface])
        vlan_mtu = random.randint(new_mtu + 1, new_mtu * 2)
        vlan1_interface.params = {'mtu': vlan_mtu}
        vlan1_interface.save()
        vlan2_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[physical_interface])
        physical_interface.params = {'mtu': new_mtu}
        physical_interface.save()
        self.assertEquals({
            'mtu': new_mtu,
            }, reload_object(vlan1_interface).params)
        self.assertEquals('', reload_object(vlan2_interface).params)

    def test__updates_parents_mtu(self):
        node = factory.make_Node()
        physical1_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical2_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        physical3_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[
                physical1_interface, physical2_interface, physical3_interface])
        # Smaller MTU will be set to larger MTU.
        physical1_mtu = random.randint(800, 1999)
        physical1_interface.params = {'mtu': physical1_mtu}
        physical1_interface.save()
        # Larger MTU will be left alone.
        physical2_mtu = random.randint(4000, 8000)
        physical2_interface.params = {'mtu': physical2_mtu}
        physical2_interface.save()
        # In between the smaller and larger MTU.
        bond_mtu = random.randint(2000, 3999)
        bond_interface.params = {'mtu': bond_mtu}
        bond_interface.save()
        self.assertEquals({
            'mtu': bond_mtu,
            }, reload_object(physical1_interface).params)
        self.assertEquals({
            'mtu': physical2_mtu,
            }, reload_object(physical2_interface).params)
        # Physical 3 should be set the the bond interface MTU.
        self.assertEquals({
            'mtu': bond_mtu,
            }, reload_object(physical3_interface).params)
