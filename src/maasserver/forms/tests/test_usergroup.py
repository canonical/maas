# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `UserGroupForm`."""

__all__ = []

from maasserver.forms import (
    ManageUserGroupsForm,
    UserGroupForm,
)
from maasserver.models import UserGroup
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.worker_user import get_worker_user
from metadataserver.nodeinituser import get_node_init_user


class TestManageUserGroupsForm(MAASServerTestCase):

    def test_get_users(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        form = ManageUserGroupsForm(
            data={'user': [str(user1.id), str(user2.id)]})
        self.assertTrue(form.is_valid())
        self.assertCountEqual(form.cleaned_data['user'], [user1, user2])

    def test_node_init_user_not_valid(self):
        user = get_node_init_user()
        form = ManageUserGroupsForm(data={'user': [str(user.id)]})
        self.assertFalse(form.is_valid())

    def test_worker_user_not_valid(self):
        user = get_worker_user()
        form = ManageUserGroupsForm(data={'user': [str(user.id)]})
        self.assertFalse(form.is_valid())


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
