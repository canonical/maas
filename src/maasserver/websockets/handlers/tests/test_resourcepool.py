# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.resourcepool`"""

from django.core.exceptions import ValidationError

from maasserver.enum import NODE_STATUS
from maasserver.models.resourcepool import ResourcePool
from maasserver.rbac import ALL_RESOURCES, FakeRBACClient, rbac
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.resourcepool import ResourcePoolHandler


class TestResourcePoolHandler(MAASServerTestCase):
    def enable_rbac(self):
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "http://rbac.example.com"}
        )
        client = FakeRBACClient()
        rbac._store.client = client
        rbac._store.cleared = False  # Prevent re-creation of the client
        self.rbac_store = client.store

    def test_get(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        result = handler.get({"id": pool.id})
        self.assertEqual(
            {
                "id": pool.id,
                "name": pool.name,
                "description": pool.description,
                "is_default": False,
                "created": dehydrate_datetime(pool.created),
                "updated": dehydrate_datetime(pool.updated),
                "machine_total_count": 0,
                "machine_ready_count": 0,
                "permissions": [],
            },
            result,
        )

    def test_get_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        result = handler.get({"id": pool.id})
        self.assertEqual(
            {
                "id": pool.id,
                "name": pool.name,
                "description": pool.description,
                "is_default": False,
                "created": dehydrate_datetime(pool.created),
                "updated": dehydrate_datetime(pool.updated),
                "machine_total_count": 0,
                "machine_ready_count": 0,
                "permissions": [],
            },
            result,
        )

    def test_get_rbac_fails(self):
        self.enable_rbac()
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.assertRaises(
            HandlerDoesNotExistError, handler.get, {"id": pool.id}
        )

    def test_get_machine_count(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        factory.make_Machine(pool=pool)
        result = handler.get({"id": pool.id})
        self.assertEqual(1, result["machine_total_count"])

    def test_get_machine_ready_count(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        factory.make_Machine(pool=pool, status=NODE_STATUS.NEW)
        factory.make_Machine(pool=pool, status=NODE_STATUS.READY)
        result = handler.get({"id": pool.id})
        self.assertEqual(2, result["machine_total_count"])
        self.assertEqual(1, result["machine_ready_count"])

    def test_get_is_default(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        handler = ResourcePoolHandler(factory.make_User(), {}, None)
        result = handler.get({"id": pool.id})
        self.assertTrue(result["is_default"])

    def test_list(self):
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        returned_pool_names = [data["name"] for data in handler.list({})]
        self.assertEqual(["default", pool.name], returned_pool_names)

    def test_list_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        handler = ResourcePoolHandler(user, {}, None)
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        returned_pool_names = [data["name"] for data in handler.list({})]
        self.assertEqual([pool.name], returned_pool_names)

    def test_create_annotations(self):
        handler = ResourcePoolHandler(factory.make_admin(), {}, None)
        result = handler.create(
            {
                "name": factory.make_name("pool"),
                "description": factory.make_name("description"),
            }
        )
        self.assertEqual(0, result["machine_total_count"])
        self.assertEqual(0, result["machine_ready_count"])

    def test_create_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        self.rbac_store.allow(user.username, ALL_RESOURCES, "view")
        self.rbac_store.allow(user.username, ALL_RESOURCES, "edit")
        handler = ResourcePoolHandler(user, {}, None)
        result = handler.create(
            {
                "name": factory.make_name("pool"),
                "description": factory.make_name("description"),
            }
        )
        self.assertEqual(0, result["machine_total_count"])
        self.assertEqual(0, result["machine_ready_count"])

    def test_create_rbac_requires_edit_on_all(self):
        self.enable_rbac()
        user = factory.make_User()
        self.rbac_store.allow(user.username, ALL_RESOURCES, "view")
        handler = ResourcePoolHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError,
            handler.create,
            {
                "name": factory.make_name("pool"),
                "description": factory.make_name("description"),
            },
        )

    def test_update(self):
        pool = factory.make_ResourcePool()
        new_name = factory.make_name("pool")
        handler = ResourcePoolHandler(factory.make_admin(), {}, None)
        handler.update({"id": pool.id, "name": new_name})
        pool = reload_object(pool)
        self.assertEqual(new_name, pool.name)

    def test_update_not_admin(self):
        handler = ResourcePoolHandler(factory.make_User(), {}, None)
        pool = factory.make_ResourcePool()
        self.assertRaises(
            HandlerPermissionError, handler.update, {"id": pool.id}
        )

    def test_update_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        self.rbac_store.allow(user.username, pool, "edit")
        new_name = factory.make_name("pool")
        handler = ResourcePoolHandler(user, {}, None)
        handler.update({"id": pool.id, "name": new_name})
        pool = reload_object(pool)
        self.assertEqual(new_name, pool.name)

    def test_update_rbac_no_edit(self):
        self.enable_rbac()
        user = factory.make_User()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        handler = ResourcePoolHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.update, {"id": pool.id}
        )

    def test_delete(self):
        handler = ResourcePoolHandler(factory.make_admin(), {}, None)
        pool = factory.make_ResourcePool()
        handler.delete({"id": pool.id})
        self.assertIsNone(reload_object(pool))

    def test_delete_not_admin(self):
        handler = ResourcePoolHandler(factory.make_User(), {}, None)
        pool = factory.make_ResourcePool()
        self.assertRaises(
            HandlerPermissionError, handler.delete, {"id": pool.id}
        )

    def test_delete_default_fails(self):
        pool = ResourcePool.objects.get_default_resource_pool()
        handler = ResourcePoolHandler(factory.make_admin(), {}, None)
        self.assertRaises(ValidationError, handler.delete, {"id": pool.id})

    def test_delete_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        self.rbac_store.allow(user.username, ALL_RESOURCES, "edit")
        handler = ResourcePoolHandler(user, {}, None)
        handler.delete({"id": pool.id})
        self.assertIsNone(reload_object(pool))

    def test_delete_rbac_no_edit_all(self):
        self.enable_rbac()
        user = factory.make_User()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        self.rbac_store.allow(user.username, pool, "edit")
        handler = ResourcePoolHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.delete, {"id": pool.id}
        )
