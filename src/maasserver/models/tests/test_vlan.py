# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the VLAN model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from maasserver.enum import INTERFACE_TYPE
from maasserver.models.interface import (
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class VLANTest(MAASServerTestCase):

    def test_creates_vlan(self):
        name = factory.make_name('name')
        vid = random.randint(3, 55)
        fabric = factory.make_Fabric()
        vlan = VLAN(vid=vid, name=name, fabric=fabric)
        vlan.save()
        self.assertThat(vlan, MatchesStructure.byEquality(
            vid=vid, name=name))

    def test_is_fabric_default_detects_default_vlan(self):
        fabric = factory.make_Fabric()
        factory.make_VLAN(fabric=fabric)
        vlan = fabric.vlan_set.all().order_by('id').first()
        self.assertTrue(vlan.is_fabric_default())

    def test_is_fabric_default_detects_non_default_vlan(self):
        vlan = factory.make_VLAN()
        self.assertFalse(vlan.is_fabric_default())

    def test_cant_delete_default_vlan(self):
        name = factory.make_name('name')
        fabric = factory.make_Fabric(name=name)
        with ExpectedException(ValidationError):
            fabric.get_default_vlan().delete()

    def test_manager_get_default_vlan_returns_dflt_vlan_of_dflt_fabric(self):
        factory.make_Fabric()
        vlan = VLAN.objects.get_default_vlan()
        self.assertTrue(vlan.is_fabric_default())
        self.assertTrue(vlan.fabric.is_default())

    def test_vlan_interfaces_are_deleted_when_related_vlan_is_deleted(self):
        mac = factory.make_MACAddress_with_Node()
        parent = factory.make_Interface(
            mac=mac, type=INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            vlan=vlan, type=INTERFACE_TYPE.VLAN, parents=[parent])
        vlan.delete()
        self.assertItemsEqual(
            [], VLANInterface.objects.filter(id=interface.id))

    def test_interfaces_are_reconnected_when_vlan_is_deleted(self):
        mac = factory.make_MACAddress_with_Node()
        vlan = factory.make_VLAN()
        fabric = vlan.fabric
        interface = factory.make_Interface(
            mac=mac, vlan=vlan, type=INTERFACE_TYPE.PHYSICAL)
        vlan.delete()
        reconnected_interfaces = PhysicalInterface.objects.filter(
            id=interface.id)
        self.assertItemsEqual([interface], reconnected_interfaces)
        reconnected_interface = reconnected_interfaces[0]
        self.assertEqual(
            reconnected_interface.vlan, fabric.get_default_vlan())

    def test_raises_integrity_error_if_reconnecting_fails(self):
        # Here we test a corner case: we test that the DB refuses to
        # leave an interface without a VLAN in case the reconnection
        # fails when a VLAN is deleted.
        mac = factory.make_MACAddress_with_Node()
        vlan = factory.make_VLAN()
        # Break 'manage_connected_interfaces'.
        self.patch(vlan, 'manage_connected_interfaces')
        factory.make_Interface(
            mac=mac, vlan=vlan, type=INTERFACE_TYPE.PHYSICAL)
        with ExpectedException(ProtectedError):
            vlan.delete()

    def test_cluster_interfaces_are_reconnected_when_vlan_is_deleted(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        nodegroup = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(nodegroup=nodegroup, vlan=vlan)
        vlan.delete()
        reconnected_interfaces = NodeGroupInterface.objects.filter(
            id=ngi.id)
        self.assertItemsEqual([ngi], reconnected_interfaces)
        reconnected_interface = reconnected_interfaces[0]
        self.assertEqual(
            reconnected_interface.vlan, fabric.get_default_vlan())


class VLANVidValidationTest(MAASServerTestCase):

    scenarios = [
        ('0', {'vid': 0, 'valid': True}),
        ('12', {'vid': 12, 'valid': True}),
        ('250', {'vid': 250, 'valid': True}),
        ('3000', {'vid': 3000, 'valid': True}),
        ('4095', {'vid': 4095, 'valid': True}),
        ('-23', {'vid': -23, 'valid': False}),
        ('4096', {'vid': 4096, 'valid': False}),
        ('10000', {'vid': 10000, 'valid': False}),
    ]

    def test_validates_vid(self):
        fabric = factory.make_Fabric()
        # Update the VID of the default VLAN so that it doesn't clash with
        # the VIDs we're testing here.
        default_vlan = fabric.get_default_vlan()
        default_vlan.vid = 999
        default_vlan.save()
        name = factory.make_name('name')
        vlan = VLAN(vid=self.vid, name=name, fabric=fabric)
        if self.valid:
            # No exception.
            self.assertIsNone(vlan.save())

        else:
            with ExpectedException(ValidationError):
                vlan.save()
