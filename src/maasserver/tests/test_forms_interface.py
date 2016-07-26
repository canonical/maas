# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Interface forms."""

__all__ = []

import random

from django.core.exceptions import ValidationError
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.forms_interface import (
    BOND_LACP_RATE_CHOICES,
    BOND_MODE_CHOICES,
    BOND_XMIT_HASH_POLICY_CHOICES,
    BondInterfaceForm,
    BridgeInterfaceForm,
    ControllerInterfaceForm,
    InterfaceForm,
    PhysicalInterfaceForm,
    VLANInterfaceForm,
)
from maasserver.models.interface import build_vlan_interface_name
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import compose_invalid_choice_text
from maasserver.utils.orm import reload_object
from testtools import ExpectedException
from testtools.matchers import MatchesStructure


class GetInterfaceFormTests(MAASServerTestCase):

    scenarios = [
        ('physical',
            {'type': INTERFACE_TYPE.PHYSICAL, 'form': PhysicalInterfaceForm}),
        ('bond',
            {'type': INTERFACE_TYPE.BOND, 'form': BondInterfaceForm}),
        ('vlan',
            {'type': INTERFACE_TYPE.VLAN, 'form': VLANInterfaceForm}),
    ]

    def test_get_interface_form_returns_form(self):
        self.assertEqual(
            self.form, InterfaceForm.get_interface_form(self.type))


class GetInterfaceFormErrorTests(MAASServerTestCase):

    def test_get_interface_form_returns_form(self):
        with ExpectedException(ValidationError):
            InterfaceForm.get_interface_form(factory.make_name())


class ControllerInterfaceFormTest(MAASServerTestCase):

    scenarios = (
        ("region", {
            "maker": factory.make_RegionController,
        }),
        ("rack", {
            "maker": factory.make_RackController,
        }),
        ("region_rack", {
            "maker": factory.make_RegionRackController,
        })
    )

    def test__edits_interface(self):
        node = self.maker()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        new_vlan = factory.make_VLAN(vid=33)
        form = ControllerInterfaceForm(
            instance=interface,
            data={
                'vlan': new_vlan.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface.name, vlan=new_vlan, enabled=interface.enabled))

    def test__allows_no_vlan(self):
        node = self.maker()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        form = ControllerInterfaceForm(
            instance=interface,
            data={
                'vlan': None,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface.name, vlan=None, enabled=interface.enabled))


class PhysicalInterfaceFormTest(MAASServerTestCase):

    def test__creates_physical_interface(self):
        node = factory.make_Node()
        mac_address = factory.make_mac_address()
        interface_name = 'eth0'
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        form = PhysicalInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'mac_address': mac_address,
                'vlan': vlan.id,
                'tags': ",".join(tags),
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                node=node, mac_address=mac_address, name=interface_name,
                type=INTERFACE_TYPE.PHYSICAL, tags=tags))
        self.assertItemsEqual([], interface.parents.all())

    def test__creates_physical_interface_disconnected(self):
        node = factory.make_Node()
        mac_address = factory.make_mac_address()
        interface_name = 'eth0'
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        form = PhysicalInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'mac_address': mac_address,
                'tags': ",".join(tags),
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                node=node, mac_address=mac_address, name=interface_name,
                type=INTERFACE_TYPE.PHYSICAL, tags=tags, vlan=None))
        self.assertItemsEqual([], interface.parents.all())

    def test__create_ensures_link_up(self):
        node = factory.make_Node()
        mac_address = factory.make_mac_address()
        interface_name = 'eth0'
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        form = PhysicalInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'mac_address': mac_address,
                'vlan': vlan.id,
                'tags': ",".join(tags),
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertIsNotNone(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY))

    def test__requires_mac_address(self):
        interface_name = 'eth0'
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        form = PhysicalInterfaceForm(
            node=factory.make_Node(),
            data={
                'name': interface_name,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['mac_address'], form.errors.keys(), form.errors)
        self.assertIn(
            "This field is required.",
            form.errors['mac_address'][0])

    def test_rejects_interface_with_duplicate_name(self):
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, vlan=vlan)
        mac_address = factory.make_mac_address()
        form = PhysicalInterfaceForm(
            node=interface.node,
            data={
                'name': interface.name,
                'mac_address': mac_address,
                'vlan': interface.vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['name'], form.errors.keys(), form.errors)
        self.assertIn(
            "already has an interface named '%s'." % interface.name,
            form.errors['name'][0])

    def test_rejects_interface_on_tagged_vlan(self):
        fabric = factory.make_Fabric()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=fabric.get_default_vlan())
        vlan = factory.make_VLAN(fabric=fabric)
        mac_address = factory.make_mac_address()
        form = PhysicalInterfaceForm(
            node=interface.node,
            data={
                'name': factory.make_name("eth"),
                'mac_address': mac_address,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['vlan'], form.errors.keys(), form.errors)
        self.assertIn(
            "A physical interface can only belong to an untagged VLAN.",
            form.errors['vlan'][0])

    def test_allows_interface_on_tagged_vlan_for_device(self):
        device = factory.make_Device()
        fabric = factory.make_Fabric()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=device, vlan=fabric.get_default_vlan())
        vlan = factory.make_VLAN(fabric=fabric)
        mac_address = factory.make_mac_address()
        form = PhysicalInterfaceForm(
            node=device,
            data={
                'name': factory.make_name("eth"),
                'mac_address': mac_address,
                'vlan': vlan.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEquals(vlan, interface.vlan)

    def test__rejects_parents(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        form = PhysicalInterfaceForm(
            node=parent.node,
            data={
                'name': factory.make_name("eth"),
                'mac_address': factory.make_mac_address(),
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['parents'], form.errors.keys(), form.errors)
        self.assertIn(
            "A physical interface cannot have parents.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name='eth0')
        new_name = 'eth1'
        new_fabric = factory.make_Fabric()
        new_vlan = new_fabric.get_default_vlan()
        form = PhysicalInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'vlan': new_vlan.id,
                'enabled': False,
                'tags': "",
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=new_name, vlan=new_vlan, enabled=False, tags=[]))
        self.assertItemsEqual([], interface.parents.all())

    def test__edits_interface_disconnected(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name='eth0')
        new_name = 'eth1'
        form = PhysicalInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'vlan': None,
                'enabled': False,
                'tags': "",
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=new_name, vlan=None, enabled=False, tags=[]))
        self.assertItemsEqual([], interface.parents.all())

    def test__create_sets_interface_parameters(self):
        node = factory.make_Node()
        mac_address = factory.make_mac_address()
        interface_name = 'eth0'
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        mtu = random.randint(1000, 2000)
        accept_ra = factory.pick_bool()
        autoconf = factory.pick_bool()
        form = PhysicalInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'mac_address': mac_address,
                'vlan': vlan.id,
                'tags': ",".join(tags),
                'mtu': mtu,
                'accept_ra': accept_ra,
                'autoconf': autoconf,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "mtu": mtu,
            "accept_ra": accept_ra,
            "autoconf": autoconf,
            }, interface.params)

    def test__update_doesnt_change_interface_parameters(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name='eth0')
        mtu = random.randint(1000, 2000)
        accept_ra = factory.pick_bool()
        autoconf = factory.pick_bool()
        interface.params = {
            "mtu": mtu,
            "accept_ra": accept_ra,
            "autoconf": autoconf,
        }
        new_name = 'eth1'
        new_fabric = factory.make_Fabric()
        new_vlan = new_fabric.get_default_vlan()
        form = PhysicalInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'vlan': new_vlan.id,
                'enabled': False,
                'tags': "",
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "mtu": mtu,
            "accept_ra": accept_ra,
            "autoconf": autoconf,
            }, interface.params)

    def test__update_does_change_interface_parameters(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name='eth0')
        mtu = random.randint(1000, 2000)
        accept_ra = factory.pick_bool()
        autoconf = factory.pick_bool()
        interface.params = {
            "mtu": mtu,
            "accept_ra": accept_ra,
            "autoconf": autoconf,
        }
        new_mtu = random.randint(1000, 2000)
        new_accept_ra = not accept_ra
        new_autoconf = not autoconf
        form = PhysicalInterfaceForm(
            instance=interface,
            data={
                "mtu": new_mtu,
                "accept_ra": new_accept_ra,
                "autoconf": new_autoconf,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "mtu": new_mtu,
            "accept_ra": new_accept_ra,
            "autoconf": new_autoconf,
            }, interface.params)

    def test__update_allows_clearing_interface_parameters(self):
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name='eth0')
        mtu = random.randint(1000, 2000)
        accept_ra = factory.pick_bool()
        autoconf = factory.pick_bool()
        interface.params = {
            "mtu": mtu,
            "accept_ra": accept_ra,
            "autoconf": autoconf,
        }
        form = PhysicalInterfaceForm(
            instance=interface,
            data={
                "mtu": "",
                "accept_ra": "",
                "autoconf": "",
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({}, interface.params)


class VLANInterfaceFormTest(MAASServerTestCase):

    def test__creates_vlan_interface(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(fabric=parent.vlan.fabric, vid=10)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        interface_name = build_vlan_interface_name(parent, vlan)
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface_name, type=INTERFACE_TYPE.VLAN))
        self.assertItemsEqual([parent], interface.parents.all())

    def test__create_ensures_link_up(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(fabric=parent.vlan.fabric, vid=10)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertIsNotNone(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY))

    def test__create_rejects_interface_without_vlan(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['vlan'], form.errors.keys(), form.errors)
        self.assertIn(
            "A VLAN interface must be connected to a tagged VLAN.",
            form.errors['vlan'][0])

    def test_rejects_interface_with_duplicate_name(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(fabric=parent.vlan.fabric, vid=10)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan, parents=[parent])
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['name'], form.errors.keys(), form.errors)
        self.assertIn(
            "already has an interface named '%s'." % interface.name,
            form.errors['name'][0])

    def test_rejects_interface_on_default_fabric(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = parent.vlan.fabric.get_default_vlan()
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['vlan'], form.errors.keys(), form.errors)
        self.assertIn(
            "A VLAN interface can only belong to a tagged VLAN.",
            form.errors['vlan'][0])

    def test__rejects_no_parents(self):
        vlan = factory.make_VLAN(vid=10)
        form = VLANInterfaceForm(
            node=factory.make_Node(),
            data={
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "A VLAN interface must have exactly one parent.",
            form.errors['parents'][0])

    def test__rejects_vlan_parent(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(fabric=parent.vlan.fabric, vid=10)
        vlan_parent = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan, parents=[parent])
        other_vlan = factory.make_VLAN(fabric=parent.vlan.fabric, vid=11)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': other_vlan.id,
                'parents': [vlan_parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "VLAN interface can't have another VLAN interface as parent.",
            form.errors['parents'][0])

    def test__rejects_no_vlan(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': None,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['vlan'], form.errors.keys())
        self.assertIn(
            "A VLAN interface must be connected to a tagged VLAN.",
            form.errors['vlan'][0])

    def test__rejects_vlan_not_on_same_fabric(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        factory.make_VLAN(fabric=parent.vlan.fabric, vid=10)
        other_vlan = factory.make_VLAN()
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': other_vlan.id,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['vlan'], form.errors.keys())
        self.assertIn(
            "A VLAN interface can only belong to a tagged VLAN on "
            "the same fabric as its parent interface.",
            form.errors['vlan'][0])

    def test__rejects_parent_on_bond(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        bond = factory.make_Interface(INTERFACE_TYPE.BOND, parents=[parent])
        vlan = factory.make_VLAN(fabric=bond.vlan.fabric, vid=10)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "A VLAN interface can't have a parent that is already in a bond.",
            form.errors['parents'][0])

    def test__rejects_more_than_one_parent(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        vlan = factory.make_VLAN(vid=10)
        form = VLANInterfaceForm(
            node=parent1.node,
            data={
                'vlan': vlan.id,
                'parents': [parent1.id, parent2.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "A VLAN interface must have exactly one parent.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        new_vlan = factory.make_VLAN(fabric=interface.vlan.fabric, vid=33)
        form = VLANInterfaceForm(
            instance=interface,
            data={
                'vlan': new_vlan.id
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name="%s.%d" % (parent.get_name(), new_vlan.vid),
                vlan=new_vlan, type=INTERFACE_TYPE.VLAN))
        self.assertItemsEqual([parent], interface.parents.all())


class BondInterfaceFormTest(MAASServerTestCase):

    def test__error_with_invalid_bond_mode(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        bond_mode = factory.make_name("bond_mode")
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
                'bond_mode': bond_mode,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            "bond_mode": [
                compose_invalid_choice_text(
                    "bond_mode", BOND_MODE_CHOICES) % {"value": bond_mode}],
            }, form.errors)

    def test__creates_bond_interface(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface_name, type=INTERFACE_TYPE.BOND,
                vlan=parent1.vlan))
        self.assertIn(
            interface.mac_address, [parent1.mac_address, parent2.mac_address])
        self.assertItemsEqual([parent1, parent2], interface.parents.all())

    def test__create_removes_parent_links_and_sets_link_up_on_bond(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent1.ensure_link_up()
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        parent2.ensure_link_up()
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual(
            0,
            parent1.ip_addresses.exclude(
                alloc_type=IPADDRESS_TYPE.DISCOVERED).count())
        self.assertEqual(
            0,
            parent2.ip_addresses.exclude(
                alloc_type=IPADDRESS_TYPE.DISCOVERED).count())
        self.assertIsNotNone(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY))

    def test__creates_bond_interface_with_parent_mac_address(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
                'mac_address': parent1.mac_address,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface_name, mac_address=parent1.mac_address,
                type=INTERFACE_TYPE.BOND))
        self.assertItemsEqual([parent1, parent2], interface.parents.all())

    def test__creates_bond_interface_with_default_bond_params(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "bond_mode": "balance-rr",
            "bond_miimon": 100,
            "bond_downdelay": 0,
            "bond_updelay": 0,
            "bond_lacp_rate": "slow",
            "bond_xmit_hash_policy": "layer2",
            }, interface.params)

    def test__creates_bond_interface_with_bond_params(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        bond_mode = factory.pick_choice(BOND_MODE_CHOICES)
        bond_miimon = random.randint(0, 1000)
        bond_downdelay = random.randint(0, 1000)
        bond_updelay = random.randint(0, 1000)
        bond_lacp_rate = factory.pick_choice(BOND_LACP_RATE_CHOICES)
        bond_xmit_hash_policy = factory.pick_choice(
            BOND_XMIT_HASH_POLICY_CHOICES)
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
                'bond_mode': bond_mode,
                'bond_miimon': bond_miimon,
                'bond_downdelay': bond_downdelay,
                'bond_updelay': bond_updelay,
                'bond_lacp_rate': bond_lacp_rate,
                'bond_xmit_hash_policy': bond_xmit_hash_policy,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "bond_mode": bond_mode,
            "bond_miimon": bond_miimon,
            "bond_downdelay": bond_downdelay,
            "bond_updelay": bond_updelay,
            "bond_lacp_rate": bond_lacp_rate,
            "bond_xmit_hash_policy": bond_xmit_hash_policy,
            }, interface.params)

    def test__rejects_no_parents(self):
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=factory.make_Node(),
            data={
                'name': interface_name,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents', 'mac_address'], form.errors.keys())
        self.assertIn(
            "A bond interface must have one or more parents.",
            form.errors['parents'][0])

    def test__rejects_when_vlan_not_untagged(self):
        interface_name = factory.make_name()
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(fabric=parent.vlan.fabric)
        form = BondInterfaceForm(
            node=parent.node,
            data={
                'name': interface_name,
                'parents': [parent.id],
                'mac_address': parent.mac_address,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['vlan'], form.errors.keys())
        self.assertIn(
            "A bond interface can only belong to an untagged VLAN.",
            form.errors['vlan'][0])

    def test__rejects_when_parents_already_have_children(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth0")
        factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[parent1])
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth1", vlan=parent1.vlan)
        factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[parent2])
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id]
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn(
            "Interfaces already in-use: eth0, eth1.",
            form.errors['parents'][0])

    def test__rejects_when_parents_not_in_same_vlan(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth0")
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth1")
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id]
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals(
            "All parents must belong to the same VLAN.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent1, parent2])
        new_fabric = factory.make_Fabric()
        new_vlan = new_fabric.get_default_vlan()
        new_name = factory.make_name()
        new_parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        form = BondInterfaceForm(
            instance=interface,
            data={
                'vlan': new_vlan.id,
                'name': new_name,
                'parents': [parent1.id, parent2.id, new_parent.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac_address=interface.mac_address, name=new_name,
                vlan=new_vlan, type=INTERFACE_TYPE.BOND))
        self.assertItemsEqual(
            [parent1, parent2, new_parent], interface.parents.all())
        self.assertItemsEqual([new_vlan], set(
            reload_object(parent).vlan
            for parent in [parent1, parent2, new_parent]
        ))

    def test__edits_interface_allows_disconnected(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        form = BondInterfaceForm(
            instance=interface,
            data={
                'vlan': None,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac_address=interface.mac_address, vlan=None,
                type=INTERFACE_TYPE.BOND))

    def test__edits_interface_removes_parents(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        parent3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent1, parent2, parent3])
        new_name = factory.make_name()
        form = BondInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac_address=interface.mac_address, name=new_name,
                type=INTERFACE_TYPE.BOND))
        self.assertItemsEqual(
            [parent1, parent2], interface.parents.all())

    def test__edits_interface_updates_mac_address_when_parent_removed(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        parent3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=parent3.mac_address,
            parents=[parent1, parent2, parent3])
        new_name = factory.make_name()
        form = BondInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=new_name, type=INTERFACE_TYPE.BOND))
        self.assertItemsEqual(
            [parent1, parent2], interface.parents.all())
        self.assertIn(
            interface.mac_address, [parent1.mac_address, parent2.mac_address])

    def test__edit_doesnt_overwrite_params(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent1, parent2])
        bond_mode = factory.pick_choice(BOND_MODE_CHOICES)
        bond_miimon = random.randint(0, 1000)
        bond_downdelay = random.randint(0, 1000)
        bond_updelay = random.randint(0, 1000)
        bond_lacp_rate = factory.pick_choice(BOND_LACP_RATE_CHOICES)
        bond_xmit_hash_policy = factory.pick_choice(
            BOND_XMIT_HASH_POLICY_CHOICES)
        interface.params = {
            "bond_mode": bond_mode,
            "bond_miimon": bond_miimon,
            "bond_downdelay": bond_downdelay,
            "bond_updelay": bond_updelay,
            "bond_lacp_rate": bond_lacp_rate,
            "bond_xmit_hash_policy": bond_xmit_hash_policy,
        }
        interface.save()
        new_name = factory.make_name()
        form = BondInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "bond_mode": bond_mode,
            "bond_miimon": bond_miimon,
            "bond_downdelay": bond_downdelay,
            "bond_updelay": bond_updelay,
            "bond_lacp_rate": bond_lacp_rate,
            "bond_xmit_hash_policy": bond_xmit_hash_policy,
            }, interface.params)

    def test__edit_does_overwrite_params(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent1, parent2])
        bond_mode = factory.pick_choice(BOND_MODE_CHOICES)
        bond_miimon = random.randint(0, 1000)
        bond_downdelay = random.randint(0, 1000)
        bond_updelay = random.randint(0, 1000)
        bond_lacp_rate = factory.pick_choice(BOND_LACP_RATE_CHOICES)
        bond_xmit_hash_policy = factory.pick_choice(
            BOND_XMIT_HASH_POLICY_CHOICES)
        interface.params = {
            "bond_mode": bond_mode,
            "bond_miimon": bond_miimon,
            "bond_downdelay": bond_downdelay,
            "bond_updelay": bond_updelay,
            "bond_lacp_rate": bond_lacp_rate,
            "bond_xmit_hash_policy": bond_xmit_hash_policy,
        }
        interface.save()
        new_name = factory.make_name()
        new_bond_mode = factory.pick_choice(BOND_MODE_CHOICES)
        new_bond_miimon = random.randint(0, 1000)
        new_bond_downdelay = random.randint(0, 1000)
        new_bond_updelay = random.randint(0, 1000)
        new_bond_lacp_rate = factory.pick_choice(BOND_LACP_RATE_CHOICES)
        new_bond_xmit_hash_policy = factory.pick_choice(
            BOND_XMIT_HASH_POLICY_CHOICES)
        form = BondInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'bond_mode': new_bond_mode,
                'bond_miimon': new_bond_miimon,
                'bond_downdelay': new_bond_downdelay,
                'bond_updelay': new_bond_updelay,
                'bond_lacp_rate': new_bond_lacp_rate,
                'bond_xmit_hash_policy': new_bond_xmit_hash_policy,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "bond_mode": new_bond_mode,
            "bond_miimon": new_bond_miimon,
            "bond_downdelay": new_bond_downdelay,
            "bond_updelay": new_bond_updelay,
            "bond_lacp_rate": new_bond_lacp_rate,
            "bond_xmit_hash_policy": new_bond_xmit_hash_policy,
            }, interface.params)

    def test__edit_allows_zero_params(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent1, parent2])
        bond_mode = factory.pick_choice(BOND_MODE_CHOICES)
        bond_miimon = random.randint(0, 1000)
        bond_downdelay = random.randint(0, 1000)
        bond_updelay = random.randint(0, 1000)
        bond_lacp_rate = factory.pick_choice(BOND_LACP_RATE_CHOICES)
        bond_xmit_hash_policy = factory.pick_choice(
            BOND_XMIT_HASH_POLICY_CHOICES)
        interface.params = {
            "bond_mode": bond_mode,
            "bond_miimon": bond_miimon,
            "bond_downdelay": bond_downdelay,
            "bond_updelay": bond_updelay,
            "bond_lacp_rate": bond_lacp_rate,
            "bond_xmit_hash_policy": bond_xmit_hash_policy,
        }
        interface.save()
        new_name = factory.make_name()
        new_bond_mode = factory.pick_choice(BOND_MODE_CHOICES)
        new_bond_miimon = 0
        new_bond_downdelay = 0
        new_bond_updelay = 0
        new_bond_lacp_rate = factory.pick_choice(BOND_LACP_RATE_CHOICES)
        new_bond_xmit_hash_policy = factory.pick_choice(
            BOND_XMIT_HASH_POLICY_CHOICES)
        form = BondInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'bond_mode': new_bond_mode,
                'bond_miimon': new_bond_miimon,
                'bond_downdelay': new_bond_downdelay,
                'bond_updelay': new_bond_updelay,
                'bond_lacp_rate': new_bond_lacp_rate,
                'bond_xmit_hash_policy': new_bond_xmit_hash_policy,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual({
            "bond_mode": new_bond_mode,
            "bond_miimon": new_bond_miimon,
            "bond_downdelay": new_bond_downdelay,
            "bond_updelay": new_bond_updelay,
            "bond_lacp_rate": new_bond_lacp_rate,
            "bond_xmit_hash_policy": new_bond_xmit_hash_policy,
            }, interface.params)


class BridgeInterfaceFormTest(MAASServerTestCase):

    def test__creates_bridge_interface(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        form = BridgeInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface_name, type=INTERFACE_TYPE.BRIDGE))
        self.assertIn(
            interface.mac_address, [parent1.mac_address, parent2.mac_address])
        self.assertItemsEqual([parent1, parent2], interface.parents.all())

    def test__create_removes_parent_links_and_sets_link_up_on_bridge(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent1.ensure_link_up()
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        parent2.ensure_link_up()
        interface_name = factory.make_name()
        form = BridgeInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual(
            0,
            parent1.ip_addresses.exclude(
                alloc_type=IPADDRESS_TYPE.DISCOVERED).count())
        self.assertEqual(
            0,
            parent2.ip_addresses.exclude(
                alloc_type=IPADDRESS_TYPE.DISCOVERED).count())
        self.assertIsNotNone(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY))

    def test__creates_bridge_interface_with_parent_mac_address(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface_name = factory.make_name()
        form = BridgeInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id],
                'mac_address': parent1.mac_address,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface_name, mac_address=parent1.mac_address,
                type=INTERFACE_TYPE.BRIDGE))
        self.assertItemsEqual([parent1, parent2], interface.parents.all())

    def test__rejects_no_parents(self):
        interface_name = factory.make_name()
        form = BridgeInterfaceForm(
            node=factory.make_Node(),
            data={
                'name': interface_name,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents', 'mac_address'], form.errors.keys())
        self.assertIn(
            "A bridge interface must have one or more parents.",
            form.errors['parents'][0])

    def test__rejects_when_parents_already_have_children(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth0")
        factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[parent1])
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth1", vlan=parent1.vlan)
        factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[parent2])
        interface_name = factory.make_name()
        form = BridgeInterfaceForm(
            node=node,
            data={
                'name': interface_name,
                'parents': [parent1.id, parent2.id]
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn(
            "Interfaces already in-use: eth0, eth1.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            parents=[parent1, parent2])
        new_fabric = factory.make_Fabric()
        new_vlan = new_fabric.get_default_vlan()
        new_name = factory.make_name()
        new_parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        form = BridgeInterfaceForm(
            instance=interface,
            data={
                'vlan': new_vlan.id,
                'name': new_name,
                'parents': [parent1.id, parent2.id, new_parent.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac_address=interface.mac_address, name=new_name,
                vlan=new_vlan, type=INTERFACE_TYPE.BRIDGE))
        self.assertItemsEqual(
            [parent1, parent2, new_parent], interface.parents.all())

    def test__edits_interface_allows_disconnected(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node, vlan=parent1.vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            parents=[parent1, parent2])
        form = BridgeInterfaceForm(
            instance=interface,
            data={
                'vlan': None,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac_address=interface.mac_address,
                vlan=None, type=INTERFACE_TYPE.BRIDGE))

    def test__edits_interface_removes_parents(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        parent3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            parents=[parent1, parent2, parent3])
        new_name = factory.make_name()
        form = BridgeInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac_address=interface.mac_address, name=new_name,
                type=INTERFACE_TYPE.BRIDGE))
        self.assertItemsEqual(
            [parent1, parent2], interface.parents.all())

    def test__edits_interface_updates_mac_address_when_parent_removed(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        parent3 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, mac_address=parent3.mac_address,
            parents=[parent1, parent2, parent3])
        new_name = factory.make_name()
        form = BridgeInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=new_name, type=INTERFACE_TYPE.BRIDGE))
        self.assertItemsEqual(
            [parent1, parent2], interface.parents.all())
        self.assertIn(
            interface.mac_address, [parent1.mac_address, parent2.mac_address])
