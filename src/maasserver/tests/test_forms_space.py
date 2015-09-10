# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Space forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms_space import SpaceForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestSpaceForm(MAASServerTestCase):

    def test__requires_name(self):
        form = SpaceForm({})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "name": ["This field is required."]
            }, form.errors)

    def test__creates_space(self):
        space_name = factory.make_name("space")
        form = SpaceForm({
            "name": space_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        space = form.save()
        self.assertEquals(space_name, space.name)

    def test__doest_require_name_on_update(self):
        space = factory.make_Fabric()
        form = SpaceForm(instance=space, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_space(self):
        new_name = factory.make_name("space")
        space = factory.make_Fabric()
        form = SpaceForm(instance=space, data={
            "name": new_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEquals(new_name, reload_object(space).name)
