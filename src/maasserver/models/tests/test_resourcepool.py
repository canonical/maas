# Copyright 2013-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test ResourcePool objects."""

from django.core.exceptions import ValidationError
from maasserver.models.resourcepool import (
    DEFAULT_RESOURCEPOOL_DESCRIPTION,
    DEFAULT_RESOURCEPOOL_NAME,
    ResourcePool,
)
from maasserver.models.role import Role
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.worker_user import get_worker_user
from metadataserver.nodeinituser import get_node_init_user


class TestResourcePoolManager(MAASServerTestCase):
    """Tests for `ResourcePool` manager."""

    def test_get_default_resource_pool_returns_default_pool(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        self.assertEqual(pool.id, 0)
        self.assertEqual(pool.name, DEFAULT_RESOURCEPOOL_NAME)
        self.assertEqual(pool.description, DEFAULT_RESOURCEPOOL_DESCRIPTION)
        self.assertIsNotNone(pool.created)
        self.assertIsNotNone(pool.updated)

    def test_get_default_resource_pool_ignores_other_pools(self):
        factory.make_ResourcePool()
        self.assertEqual(
            ResourcePool.objects.get_default_resource_pool().name,
            DEFAULT_RESOURCEPOOL_NAME)

    def test_get_user_resource_pools(self):
        user = factory.make_User()
        default_pool = ResourcePool.objects.get_default_resource_pool()
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        factory.make_ResourcePool()  # a pool the user doesn't have access to

        role = factory.make_Role()
        role.users.add(user)
        role.resource_pools.add(pool1)
        role.resource_pools.add(pool2)
        self.assertCountEqual(
            ResourcePool.objects.get_user_resource_pools(user),
            [default_pool, pool1, pool2])

    def test_user_can_access_pool(self):
        user = factory.make_User()
        pool = factory.make_ResourcePool()
        manager = ResourcePool.objects
        self.assertFalse(manager.user_can_access_pool(user, pool))
        pool.grant_user(user)
        self.assertTrue(manager.user_can_access_pool(user, pool))

    def test_user_can_access_pool_worker_user(self):
        user = get_worker_user()
        pool = factory.make_ResourcePool()
        self.assertTrue(
            ResourcePool.objects.user_can_access_pool(user, pool))

    def test_user_can_access_pool_node_init_user(self):
        user = get_node_init_user()
        pool = factory.make_ResourcePool()
        self.assertTrue(
            ResourcePool.objects.user_can_access_pool(user, pool))


class TestResourcePool(MAASServerTestCase):

    def test_init(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        pool = ResourcePool(name=name, description=description)
        pool.save()
        pool = reload_object(pool)
        self.assertEqual(pool.name, name)
        self.assertEqual(pool.description, description)

    def test_is_default_true(self):
        self.assertTrue(
            ResourcePool.objects.get_default_resource_pool().is_default())

    def test_is_default_false(self):
        self.assertFalse(factory.make_ResourcePool().is_default())

    def test_delete(self):
        pool = factory.make_ResourcePool()
        pool.delete()
        self.assertIsNone(reload_object(pool))

    def test_delete_removes_role(self):
        pool = factory.make_ResourcePool()
        role = pool.role_set.first()
        pool.delete()
        self.assertIsNone(reload_object(role))

    def test_delete_default_fails(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        self.assertRaises(ValidationError, pool.delete)

    def test_delete_pool_with_machines_fails(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        factory.make_Node(pool=pool)
        self.assertRaises(ValidationError, pool.delete)

    def test_create_adds_predefined_role(self):
        name = factory.make_name()
        pool = factory.make_ResourcePool(name=name)
        role = Role.objects.get(name='role-{}'.format(name))
        self.assertCountEqual(role.resource_pools.all(), [pool])

    def test_grant_user(self):
        user = factory.make_User()
        pool = factory.make_ResourcePool()
        pool.grant_user(user)
        self.assertIn(
            pool,
            ResourcePool.objects.get_user_resource_pools(user))

    def test_revoke_user(self):
        user = factory.make_User()
        default_pool = ResourcePool.objects.get_default_resource_pool()
        default_pool.revoke_user(user)
        self.assertCountEqual(
            ResourcePool.objects.get_user_resource_pools(user), [])

    def test_revoke_user_with_machine_in_pool_fail(self):
        user = factory.make_User()
        factory.make_Node(owner=user)
        default_pool = ResourcePool.objects.get_default_resource_pool()
        self.assertRaises(ValidationError, default_pool.revoke_user, user)
