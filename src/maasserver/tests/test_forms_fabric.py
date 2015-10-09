# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Fabric forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms_fabric import FabricForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestFabricForm(MAASServerTestCase):

    def test__creates_fabric(self):
        fabric_name = factory.make_name("fabric")
        form = FabricForm({
            "name": fabric_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        fabric = form.save()
        self.assertEquals(fabric_name, fabric.name)

    def test__doest_require_name_on_update(self):
        fabric = factory.make_Fabric()
        form = FabricForm(instance=fabric, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_fabric(self):
        new_name = factory.make_name("fabric")
        fabric = factory.make_Fabric()
        form = FabricForm(instance=fabric, data={
            "name": new_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEquals(new_name, reload_object(fabric).name)
