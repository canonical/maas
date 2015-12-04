# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Fabric forms."""

__all__ = []

from maasserver.forms_fabric import FabricForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestFabricForm(MAASServerTestCase):

    def test__creates_fabric(self):
        fabric_name = factory.make_name("fabric")
        fabric_class_type = factory.make_name("class_type")
        form = FabricForm({
            "name": fabric_name,
            "class_type": fabric_class_type,
        })
        self.assertTrue(form.is_valid(), form.errors)
        fabric = form.save()
        self.assertEqual(fabric_name, fabric.name)
        self.assertEqual(fabric_class_type, fabric.class_type)

    def test__doest_require_name_on_update(self):
        fabric = factory.make_Fabric()
        form = FabricForm(instance=fabric, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_fabric(self):
        new_name = factory.make_name("fabric")
        new_class_type = factory.make_name("class_type")
        fabric = factory.make_Fabric()
        form = FabricForm(instance=fabric, data={
            "name": new_name,
            "class_type": new_class_type,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(fabric).name)
        self.assertEqual(new_class_type, reload_object(fabric).class_type)
