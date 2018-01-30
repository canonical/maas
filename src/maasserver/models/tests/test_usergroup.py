# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test UserGroup objects."""

from django.core.exceptions import ValidationError
from maasserver.models.usergroup import (
    DEFAULT_USERGROUP_DESCRIPTION,
    DEFAULT_USERGROUP_NAME,
    UserGroup,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.worker_user import get_worker_user
from metadataserver.nodeinituser import get_node_init_user


class TestUserGroupManager(MAASServerTestCase):
    """Tests for `UserGroup` manager."""

    def test_get_default_usergroup_returns_default(self):
        group = UserGroup.objects.get_default_usergroup()
        self.assertEqual(group.id, 0)
        self.assertEqual(group.name, DEFAULT_USERGROUP_NAME)
        self.assertEqual(group.description, DEFAULT_USERGROUP_DESCRIPTION)
        self.assertIsNotNone(group.created)
        self.assertIsNotNone(group.updated)

    def test_get_default_usergroup_ignores_other_groups(self):
        factory.make_UserGroup()
        self.assertEqual(
            UserGroup.objects.get_default_usergroup().name,
            DEFAULT_USERGROUP_NAME)

    def test_user_assigned_to_default_group(self):
        default_group = UserGroup.objects.get_default_usergroup()
        user = factory.make_User()
        self.assertIn(user, default_group.users.all())

    def test_worker_user_not_in_default_group(self):
        default_group = UserGroup.objects.get_default_usergroup()
        self.assertNotIn(get_worker_user(), default_group.users.all())

    def test_node_init_user_not_in_default_group(self):
        default_group = UserGroup.objects.get_default_usergroup()
        self.assertNotIn(get_node_init_user(), default_group.users.all())


class TestUserGroup(MAASServerTestCase):

    def test_init(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        group = UserGroup(name=name, description=description)
        group.save()
        group = reload_object(group)
        self.assertEqual(group.name, name)
        self.assertEqual(group.description, description)

    def test_is_default_true(self):
        self.assertTrue(
            UserGroup.objects.get_default_usergroup().is_default())

    def test_is_default_false(self):
        self.assertFalse(factory.make_UserGroup().is_default())

    def test_delete(self):
        group = factory.make_UserGroup()
        group.delete()
        self.assertIsNone(reload_object(group))

    def test_delete_default_fails(self):
        group = UserGroup.objects.get_default_usergroup()
        self.assertRaises(ValidationError, group.delete)
