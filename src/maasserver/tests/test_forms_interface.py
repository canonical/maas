# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Interface forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maasserver.enum import INTERFACE_TYPE
from maasserver.forms_interface import (
    BondInterfaceForm,
    InterfaceForm,
    PhysicalInterfaceForm,
    VLANInterfaceForm,
)
from maasserver.models.interface import build_vlan_interface_name
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
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


class PhysicalInterfaceFormTest(MAASServerTestCase):

    def test__creates_physical_interface(self):
        node = factory.make_Node()
        mac_address = factory.make_mac_address()
        interface_name = 'eth0'
        vlan = factory.make_VLAN()
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

    def test__requires_mac_address(self):
        interface_name = 'eth0'
        vlan = factory.make_VLAN()
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
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
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

    def test__rejects_parents(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
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
        new_vlan = factory.make_VLAN(vid=33)
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


class VLANInterfaceFormTest(MAASServerTestCase):

    def test__creates_vlan_interface(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(vid=10)
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

    def test_rejects_interface_with_duplicate_name(self):
        vlan = factory.make_VLAN(vid=10)
        parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            vlan=vlan)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=vlan, parents=[parent])
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
        vlan_parent = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        vlan = factory.make_VLAN(vid=10)
        form = VLANInterfaceForm(
            node=parent.node,
            data={
                'vlan': vlan.id,
                'parents': [vlan_parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "VLAN interface can't have another VLAN interface as parent.",
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
        new_vlan = factory.make_VLAN(vid=33)
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

    def test__creates_bond_interface(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface_name = factory.make_name()
        vlan = factory.make_VLAN(vid=10)
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'vlan': vlan.id,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                name=interface_name, type=INTERFACE_TYPE.BOND))
        self.assertIn(
            interface.mac_address, [parent1.mac_address, parent2.mac_address])
        self.assertItemsEqual([parent1, parent2], interface.parents.all())

    def test__creates_bond_interface_with_parent_mac_address(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface_name = factory.make_name()
        vlan = factory.make_VLAN(vid=10)
        form = BondInterfaceForm(
            node=parent1.node,
            data={
                'name': interface_name,
                'vlan': vlan.id,
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

    def test__rejects_no_parents(self):
        vlan = factory.make_VLAN(vid=10)
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            node=factory.make_Node(),
            data={
                'name': interface_name,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents', 'mac_address'], form.errors.keys())
        self.assertIn(
            "A Bond interface must have one or more parents.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent1, parent2])
        new_vlan = factory.make_VLAN(vid=33)
        new_name = factory.make_name()
        new_parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent1.node)
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
