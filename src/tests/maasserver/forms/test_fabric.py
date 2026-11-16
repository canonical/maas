# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Fabric forms."""

from maasserver.forms.fabric import FabricForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestFabricForm(MAASServerTestCase):
    def test_creates_fabric(self):
        fabric_name = factory.make_name("fabric")
        fabric_description = factory.make_name("description")
        fabric_class_type = factory.make_name("class_type")
        form = FabricForm(
            {
                "name": fabric_name,
                "description": fabric_description,
                "class_type": fabric_class_type,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        fabric = form.save()
        self.assertEqual(fabric_name, fabric.name)
        self.assertEqual(fabric_description, fabric.description)
        self.assertEqual(fabric_class_type, fabric.class_type)

    def test_doest_require_name_on_update(self):
        fabric = factory.make_Fabric()
        form = FabricForm(instance=fabric, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_fabric(self):
        new_name = factory.make_name("fabric")
        new_fabric_description = factory.make_name("description")
        new_class_type = factory.make_name("class_type")
        fabric = factory.make_Fabric()
        form = FabricForm(
            instance=fabric,
            data={
                "name": new_name,
                "description": new_fabric_description,
                "class_type": new_class_type,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(fabric).name)
        self.assertEqual(
            new_fabric_description, reload_object(fabric).description
        )
        self.assertEqual(new_class_type, reload_object(fabric).class_type)
