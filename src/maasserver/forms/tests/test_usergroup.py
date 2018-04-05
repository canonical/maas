# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `UserGroupForm`."""

__all__ = []

from maasserver.forms import UserGroupForm
from maasserver.models import UserGroup
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestUserGroupForm(MAASServerTestCase):
    """Tests for `UserGroupForm`."""

    def test_creates_usergroup(self):
        name = factory.make_name('usergroup')
        description = factory.make_string()
        form = UserGroupForm(
            data={'name': name, 'description': description})
        form.save()
        group = UserGroup.objects.get(name=name)
        self.assertIsNotNone(group)
        self.assertEqual(group.description, description)
        self.assertTrue(group.local)

    def test_creates_usergroup_not_local(self):
        name = factory.make_name('usergroup')
        form = UserGroupForm(
            data={'name': name, 'local': False})
        form.save()
        group = UserGroup.objects.get(name=name)
        self.assertFalse(group.local)

    def test_updates_usergroup(self):
        group = factory.make_UserGroup()
        new_description = factory.make_string()
        form = UserGroupForm(
            data={'description': new_description},
            instance=group)
        form.save()
        group = reload_object(group)
        self.assertEqual(group.description, new_description)

    def test_update_usergroup_no_change_local(self):
        group = factory.make_UserGroup()
        form = UserGroupForm(data={'local': False}, instance=group)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['local'].as_data()[0].message,
            "Can't change user group type")

    def test_renames_group(self):
        group = factory.make_UserGroup()
        new_name = factory.make_name('group')
        form = UserGroupForm(data={'name': new_name}, instance=group)
        form.save()
        group = reload_object(group)
        self.assertEqual(group.name, new_name)
