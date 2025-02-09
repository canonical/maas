# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Space forms."""

from maasserver.forms.space import SpaceForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestSpaceForm(MAASServerTestCase):
    def test_requires_name(self):
        form = SpaceForm({})
        self.assertTrue(form.is_valid(), form.errors)

    def test_creates_space(self):
        space_name = factory.make_name("space")
        space_description = factory.make_name("description")
        form = SpaceForm(
            {"name": space_name, "description": space_description}
        )
        self.assertTrue(form.is_valid(), form.errors)
        space = form.save()
        self.assertEqual(space_name, space.get_name())
        self.assertEqual(space_description, space.description)

    def test_doest_require_name_on_update(self):
        space = factory.make_Space()
        form = SpaceForm(instance=space, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_space(self):
        new_name = factory.make_name("space")
        new_description = factory.make_name("description")
        space = factory.make_Space()
        form = SpaceForm(
            instance=space,
            data={"name": new_name, "description": new_description},
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(space).name)
        self.assertEqual(new_description, reload_object(space).description)
