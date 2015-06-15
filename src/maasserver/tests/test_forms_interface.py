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
        mac = factory.make_MACAddress_with_Node()
        interface_name = 'eth0'
        vlan = factory.make_VLAN()
        form = PhysicalInterfaceForm(
            {
                'name': interface_name,
                'mac': mac.id,
                'vlan': vlan.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac=mac, name=interface_name, type=INTERFACE_TYPE.PHYSICAL))
        self.assertItemsEqual([], interface.parents.all())

    def test__requires_mac(self):
        interface_name = 'eth0'
        vlan = factory.make_VLAN()
        form = PhysicalInterfaceForm(
            {
                'name': interface_name,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['mac'], form.errors.keys(), form.errors)
        self.assertIn(
            "This field is required.",
            form.errors['mac'][0])

    def test_rejects_interface_with_duplicate_name(self):
        name = factory.make_name('name')
        mac = factory.make_MACAddress_with_Node()
        factory.make_Interface(
            name=name, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        new_mac = factory.make_MACAddress_with_Node(node=mac.node)
        form = PhysicalInterfaceForm(
            {
                'name': name,
                'mac': new_mac.id,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(
            ['name'], form.errors.keys(), form.errors)
        self.assertIn(
            "already has an interface named '%s'." % name,
            form.errors['name'][0])

    def test__rejects_parents(self):
        mac = factory.make_MACAddress_with_Node()
        interface_name = 'eth0'
        parent = factory.make_Interface(
            name=factory.make_name('name'), mac=mac,
            type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        form = PhysicalInterfaceForm(
            {
                'name': interface_name,
                'mac': mac.id,
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
        mac = factory.make_MACAddress_with_Node()
        vlan = factory.make_VLAN(vid=33)
        interface = factory.make_Interface(
            name='eth0', mac=mac, type=INTERFACE_TYPE.PHYSICAL,
            vlan=vlan)
        new_name = 'eth1'
        new_vlan = factory.make_VLAN(vid=33)
        form = PhysicalInterfaceForm(
            instance=interface,
            data={
                'name': new_name,
                'vlan': new_vlan.id
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac=mac, name=new_name, type=INTERFACE_TYPE.PHYSICAL))
        self.assertItemsEqual([], interface.parents.all())


class VLANInterfaceFormTest(MAASServerTestCase):

    def test__creates_vlan_interface(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            name=factory.make_name('name'), mac=mac,
            type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(vid=10)
        form = VLANInterfaceForm(
            {
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        interface_name = build_vlan_interface_name(vlan)
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac=None, name=interface_name, type=INTERFACE_TYPE.VLAN))
        self.assertItemsEqual([parent], interface.parents.all())

    def test_rejects_interface_with_duplicate_name(self):
        mac = factory.make_MACAddress_with_Node()
        vlan = factory.make_VLAN(vid=10)
        parent = factory.make_Interface(
            vlan=vlan, mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        form = VLANInterfaceForm(
            {
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
            {
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "A VLAN interface must have exactly one parent.",
            form.errors['parents'][0])

    def test__rejects_vlan_parent(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            name=factory.make_name('name'), mac=mac,
            type=INTERFACE_TYPE.VLAN)
        vlan = factory.make_VLAN(vid=10)
        form = VLANInterfaceForm(
            {
                'vlan': vlan.id,
                'parents': [parent.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "VLAN interface can't have another VLAN interface as parent.",
            form.errors['parents'][0])

    def test__rejects_more_than_one_parent(self):
        mac = factory.make_MACAddress_with_Node()
        parent1 = factory.make_Interface(
            name=factory.make_name('name'), mac=mac,
            type=INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            name=factory.make_name('name'), mac=mac,
            type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN(vid=10)
        form = VLANInterfaceForm(
            {
                'vlan': vlan.id,
                'parents': [parent1.id, parent2.id],
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "A VLAN interface must have exactly one parent.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            type=INTERFACE_TYPE.VLAN, parents=[parent])
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
                mac=None, name="vlan%d" % new_vlan.vid,
                vlan=new_vlan, type=INTERFACE_TYPE.VLAN))
        self.assertItemsEqual([parent], interface.parents.all())


class BondInterfaceFormTest(MAASServerTestCase):

    def test__creates_bond_interface(self):
        mac = factory.make_MACAddress_with_Node()
        parent1 = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        interface_name = factory.make_name()
        vlan = factory.make_VLAN(vid=10)
        form = BondInterfaceForm(
            {
                'name': interface_name,
                'vlan': vlan.id,
                'parents': [parent1.id, parent2.id],
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertThat(
            interface,
            MatchesStructure.byEquality(
                mac=None, name=interface_name, type=INTERFACE_TYPE.BOND))
        self.assertItemsEqual([parent1, parent2], interface.parents.all())

    def test__rejects_no_parents(self):
        vlan = factory.make_VLAN(vid=10)
        interface_name = factory.make_name()
        form = BondInterfaceForm(
            {
                'name': interface_name,
                'vlan': vlan.id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['parents'], form.errors.keys())
        self.assertIn(
            "A Bond interface must have two parents or more.",
            form.errors['parents'][0])

    def test__edits_interface(self):
        mac = factory.make_MACAddress_with_Node()
        parent1 = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            name=factory.make_name('name'), type=INTERFACE_TYPE.BOND,
            parents=[parent1, parent2])
        new_vlan = factory.make_VLAN(vid=33)
        new_name = factory.make_name()
        new_parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
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
                mac=None, name=new_name,
                vlan=new_vlan, type=INTERFACE_TYPE.BOND))
        self.assertItemsEqual(
            [parent1, parent2, new_parent], interface.parents.all())
