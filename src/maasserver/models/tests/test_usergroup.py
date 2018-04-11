# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test UserGroup objects."""

from django.core.exceptions import ValidationError
from maasserver.models import ResourcePool
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

    def test_get_remote_group_names(self):
        remote1 = factory.make_UserGroup(local=False)
        remote2 = factory.make_UserGroup(local=False)
        factory.make_UserGroup(local=True)
        self.assertEqual(
            UserGroup.objects.get_remote_group_names(),
            {remote1.name, remote2.name})

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
        self.assertTrue(group.local)

    def test_not_local(self):
        group = UserGroup(
            name=factory.make_name(), description=factory.make_name(),
            local=False)
        group.save()
        group = reload_object(group)
        self.assertFalse(group.local)

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

    def test_delete_with_user_losing_access_fails(self):
        user = factory.make_User()
        group = factory.make_UserGroup(users=[user])
        node = factory.make_Node(owner=user)
        factory.make_ResourcePool(groups=[group], nodes=[node])
        self.assertRaises(ValidationError, group.delete)

    def test_delete_with_user_direct_access(self):
        user = factory.make_User()
        group = factory.make_UserGroup(users=[user])
        node = factory.make_Node(owner=user)
        pool = factory.make_ResourcePool(
            groups=[group], users=[user], nodes=[node])
        group.delete()
        self.assertIn(
            pool, ResourcePool.objects.get_user_resource_pools(user))

    def test_delete_with_other_group_access(self):
        user = factory.make_User()
        group1 = factory.make_UserGroup(users=[user])
        group2 = factory.make_UserGroup(users=[user])
        node = factory.make_Node(owner=user)
        pool = factory.make_ResourcePool(groups=[group1, group2], nodes=[node])
        group1.delete()
        self.assertIn(
            pool, ResourcePool.objects.get_user_resource_pools(user))

    def test_delete_user_unrelated_resources(self):
        user = factory.make_User()
        group1 = factory.make_UserGroup(users=[user])
        group2 = factory.make_UserGroup(users=[user])
        node = factory.make_Node(owner=user)
        factory.make_ResourcePool(groups=[group1])
        pool2 = factory.make_ResourcePool(groups=[group2], nodes=[node])
        group1.delete()
        self.assertIn(
            pool2, ResourcePool.objects.get_user_resource_pools(user))

    def test_add_user(self):
        user = factory.make_User()
        group = factory.make_UserGroup()
        group.add(user)
        self.assertCountEqual(group.users.all(), [user])

    def test_add_user_already_in_group(self):
        user = factory.make_User()
        group = factory.make_UserGroup(users=[user])
        group.add(user)
        self.assertCountEqual(group.users.all(), [user])

    def test_remove_user(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        group = factory.make_UserGroup(users=[user1, user2])
        group.remove(user1)
        self.assertCountEqual(group.users.all(), [user2])

    def test_remove_user_would_lose_machine_access(self):
        user = factory.make_User()
        group = factory.make_UserGroup(users=[user])
        pool = factory.make_ResourcePool()
        factory.make_Role(pools=[pool], groups=[group])
        factory.make_Node(owner=user, pool=pool)
        self.assertRaises(ValidationError, group.remove, user)

    def test_remove_user_with_other_group_access_to_machine(self):
        user = factory.make_User()
        group1 = factory.make_UserGroup(users=[user])
        group2 = factory.make_UserGroup(users=[user])
        pool = factory.make_ResourcePool()
        factory.make_Role(pools=[pool], groups=[group1])
        factory.make_Role(pools=[pool], groups=[group2])
        factory.make_Node(owner=user, pool=pool)
        group1.remove(user)
        self.assertTrue(ResourcePool.objects.user_can_access_pool(user, pool))

    def test_remove_user_with_other_group_access_to_machine_same_role(self):
        user = factory.make_User()
        group1 = factory.make_UserGroup(users=[user])
        group2 = factory.make_UserGroup(users=[user])
        pool = factory.make_ResourcePool()
        factory.make_Role(pools=[pool], groups=[group1, group2])
        factory.make_Node(owner=user, pool=pool)
        group1.remove(user)
        self.assertTrue(ResourcePool.objects.user_can_access_pool(user, pool))

    def test_remove_user_with_direct_access_to_machine(self):
        user = factory.make_User()
        group = factory.make_UserGroup(users=[user])
        pool = factory.make_ResourcePool(users=[user])
        factory.make_Role(pools=[pool], groups=[group])
        group.remove(user)
        self.assertTrue(ResourcePool.objects.user_can_access_pool(user, pool))
