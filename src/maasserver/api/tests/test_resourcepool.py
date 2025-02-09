# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for resource pool API."""

import http.client
import json

from django.conf import settings
from django.urls import reverse

from maasserver.api import auth
from maasserver.models import ResourcePool
from maasserver.rbac import ALL_RESOURCES
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.utils.orm import reload_object


class TestResourcePoolAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            reverse("resourcepool_handler", args=[123]),
            "/MAAS/api/2.0/resourcepool/123/",
        )

    def test_POST_disallowed_for_creation(self):
        self.become_admin()
        name = factory.make_name("name")
        description = factory.make_name("description")
        response = self.client.post(
            reverse("resourcepool_handler", args=[123]),
            {"name": name, "description": description},
        )
        self.assertEqual(response.status_code, http.client.METHOD_NOT_ALLOWED)

    def test_GET_returns_pool(self):
        pool = factory.make_ResourcePool()
        response = self.client.get(
            reverse("resourcepool_handler", args=[pool.id]), {}
        )
        self.assertEqual(response.status_code, http.client.OK)
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(result["name"], pool.name)
        self.assertEqual(result["description"], pool.description)
        self.assertEqual(
            result["resource_uri"],
            f"/MAAS/api/2.0/resourcepool/{pool.id}/",
        )

    def test_PUT_updates_pool(self):
        self.become_admin()
        pool = factory.make_ResourcePool()
        new_name = factory.make_name("name")
        new_description = factory.make_name("description")
        response = self.client.put(
            reverse("resourcepool_handler", args=[pool.id]),
            {"name": new_name, "description": new_description},
        )
        self.assertEqual(response.status_code, http.client.OK)
        pool = reload_object(pool)
        self.assertEqual(pool.name, new_name)
        self.assertEqual(pool.description, new_description)

    def test_PUT_updates_pool_by_name(self):
        self.become_admin()
        pool = factory.make_ResourcePool()
        new_name = factory.make_name("name")
        new_description = factory.make_name("description")
        response = self.client.put(
            reverse("resourcepool_handler", args=[pool.name]),
            {"name": new_name, "description": new_description},
        )
        self.assertEqual(response.status_code, http.client.OK)
        pool = reload_object(pool)
        self.assertEqual(pool.name, new_name)
        self.assertEqual(pool.description, new_description)

    def test_PUT_missing(self):
        self.become_admin()
        description = factory.make_string()
        response = self.client.get(
            reverse("resourcepool_handler", args=[-1]),
            {"description": description},
        )
        self.assertEqual(response.status_code, http.client.NOT_FOUND)

    def test_PUT_requires_admin(self):
        pool = factory.make_ResourcePool()
        response = self.client.put(
            reverse("resourcepool_handler", args=[pool.id]),
            {"description": factory.make_string()},
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_DELETE_removes_pool_by_id(self):
        self.become_admin()
        pool = factory.make_ResourcePool()
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.id]), {}
        )
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        self.assertIsNone(reload_object(pool))

    def test_DELETE_removes_pool_by_name(self):
        self.become_admin()
        pool = factory.make_ResourcePool()
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.name]), {}
        )
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        self.assertIsNone(reload_object(pool))

    def test_DELETE_default_pool_denied(self):
        self.become_admin()
        response = self.client.delete(
            reverse("resourcepool_handler", args=[0]), {}
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)
        self.assertIsNotNone(ResourcePool.objects.get_default_resource_pool())

    def test_DELETE_requires_admin(self):
        pool = factory.make_ResourcePool()
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.id]), {}
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_DELETE_is_idempotent(self):
        self.become_admin()
        pool = factory.make_ResourcePool()
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.id])
        )
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        self.assertIsNone(reload_object(pool))


class TestResourcePoolAPIWithRBAC(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.store = rbac.store
        self.become_non_local()

    def test_GET_returns_pool(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        self.store.allow(self.user.username, pool, "view")
        response = self.client.get(
            reverse("resourcepool_handler", args=[pool.id]), {}
        )
        self.assertEqual(response.status_code, http.client.OK)
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(result["name"], pool.name)
        self.assertEqual(result["description"], pool.description)
        self.assertEqual(
            result["resource_uri"],
            f"/MAAS/api/2.0/resourcepool/{pool.id}/",
        )

    def test_GET_returns_forbidden(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        response = self.client.get(
            reverse("resourcepool_handler", args=[pool.id]), {}
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_PUT_updates_pool(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        self.store.allow(self.user.username, pool, "edit")
        new_name = factory.make_name("name")
        new_description = factory.make_name("description")
        response = self.client.put(
            reverse("resourcepool_handler", args=[pool.id]),
            {"name": new_name, "description": new_description},
        )
        self.assertEqual(response.status_code, http.client.OK)
        pool = reload_object(pool)
        self.assertEqual(pool.name, new_name)
        self.assertEqual(pool.description, new_description)

    def test_PUT_forbidden(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        self.store.allow(self.user.username, pool, "view")
        new_name = factory.make_name("name")
        new_description = factory.make_name("description")
        response = self.client.put(
            reverse("resourcepool_handler", args=[pool.id]),
            {"name": new_name, "description": new_description},
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_DELETE_removes_pool(self):
        pool = factory.make_ResourcePool()
        self.store.allow(self.user.username, ALL_RESOURCES, "edit")
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.id])
        )
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

    def test_DELETE_forbidden_edit_on_pool_only(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        self.store.allow(self.user.username, pool, "edit")
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.id])
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_DELETE_forbidden(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        self.store.allow(self.user.username, pool, "view")
        response = self.client.delete(
            reverse("resourcepool_handler", args=[pool.name]), {}
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)
