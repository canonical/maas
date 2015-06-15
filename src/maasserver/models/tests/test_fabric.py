# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Fabric model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.core.exceptions import ValidationError
from maasserver.models.fabric import (
    DEFAULT_FABRIC_NAME,
    Fabric,
)
from maasserver.models.vlan import (
    DEFAULT_VID,
    DEFAULT_VLAN_NAME,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class FabricTest(MAASServerTestCase):

    def test_creates_fabric_with_default_vlan(self):
        name = factory.make_name('name')
        fabric = factory.make_Fabric(name=name)
        self.assertEqual(name, fabric.name)
        default_vlan = fabric.default_vlan
        self.assertThat(default_vlan, MatchesStructure.byEquality(
            vid=DEFAULT_VID, name=DEFAULT_VLAN_NAME))

    def test_get_default_fabric_creates_default_fabric(self):
        default_fabric = Fabric.objects.get_default_fabric()
        self.assertThat(default_fabric, MatchesStructure.byEquality(
            id=0, name=DEFAULT_FABRIC_NAME))

    def test_get_default_fabric_is_idempotent(self):
        default_fabric = Fabric.objects.get_default_fabric()
        default_fabric2 = Fabric.objects.get_default_fabric()
        self.assertEqual(default_fabric.id, default_fabric2.id)

    def test_is_default_detects_default_fabric(self):
        default_fabric = Fabric.objects.get_default_fabric()
        self.assertTrue(default_fabric.is_default())

    def test_is_default_detects_non_default_fabric(self):
        name = factory.make_name('name')
        fabric = factory.make_Fabric(name=name)
        self.assertFalse(fabric.is_default())

    def test_cant_delete_default_fabric(self):
        default_fabric = Fabric.objects.get_default_fabric()
        with ExpectedException(ValidationError):
            default_fabric.delete()

    def test_can_delete_non_default_fabric(self):
        name = factory.make_name('name')
        fabric = factory.make_Fabric(name=name)
        fabric.delete()
        self.assertItemsEqual([], Fabric.objects.all())

    def test_save_rejects_default_vlan_not_in_fabric(self):
        vlan = factory.make_VLAN()
        fabric = factory.make_Fabric()
        fabric.default_vlan = vlan
        with ExpectedException(ValidationError):
            fabric.save()

    def test_save_accepts_default_vlan_in_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        fabric.default_vlan = vlan
        # No exception.
        self.assertIsNone(fabric.save())
