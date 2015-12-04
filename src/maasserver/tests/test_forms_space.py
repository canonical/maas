# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Space forms."""

__all__ = []

from maasserver.forms_space import SpaceForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestSpaceForm(MAASServerTestCase):

    def test__requires_name(self):
        form = SpaceForm({})
        self.assertTrue(form.is_valid(), form.errors)

    def test__creates_space(self):
        space_name = factory.make_name("space")
        form = SpaceForm({
            "name": space_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        space = form.save()
        self.assertEqual(space_name, space.get_name())

    def test__doest_require_name_on_update(self):
        space = factory.make_Space()
        form = SpaceForm(instance=space, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_space(self):
        new_name = factory.make_name("space")
        space = factory.make_Space()
        form = SpaceForm(instance=space, data={
            "name": new_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(space).name)
