# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for resource pools API."""

import http.client
import json
from operator import attrgetter
import random

from django.conf import settings
from django.urls import reverse

from maasserver.api import auth
from maasserver.models import ResourcePool
from maasserver.rbac import ALL_RESOURCES
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled


class TestResourcePoolsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/resourcepools/", reverse("resourcepools_handler")
        )

    def test_create_pool(self):
        self.become_admin()
        name = factory.make_name("name")
        description = factory.make_name("description")
        response = self.client.post(
            reverse("resourcepools_handler"),
            {"name": name, "description": description},
        )
        self.assertEqual(response.status_code, http.client.OK)
        pool = ResourcePool.objects.get(name=name)
        self.assertEqual(pool.description, description)

    def test_create_requires_admin(self):
        name = factory.make_name("name")
        description = factory.make_name("description")
        response = self.client.post(
            reverse("resourcepools_handler"),
            {"name": name, "description": description},
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_list_returns_pools_list(self):
        pools = [factory.make_ResourcePool() for _ in range(3)]
        # include the default pool
        pools.append(ResourcePool.objects.get_default_resource_pool())
        pools.sort(key=attrgetter("name"))
        response = self.client.get(reverse("resourcepools_handler"), {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertCountEqual(
            [
                (pool["name"], pool["description"], pool["resource_uri"])
                for pool in result
            ],
            [
                (
                    pool.name,
                    pool.description,
                    reverse("resourcepool_handler", args=[pool.id]),
                )
                for pool in pools
            ],
        )


class TestResourcePoolsAPIWithRBAC(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.store = rbac.store
        self.become_non_local()

    def test_GET_empty_when_no_access(self):
        for _ in range(3):
            factory.make_ResourcePool()
        response = self.client.get(reverse("resourcepools_handler"), {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual([], result)

    def test_GET_returns_viewable(self):
        pools = [factory.make_ResourcePool() for _ in range(3)]
        for pool in pools:
            self.store.add_pool(pool)
        viewable = random.choice(pools)
        self.store.allow(self.user.username, viewable, "view")
        response = self.client.get(reverse("resourcepools_handler"), {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertCountEqual(
            [
                (pool["name"], pool["description"], pool["resource_uri"])
                for pool in result
            ],
            [
                (
                    viewable.name,
                    viewable.description,
                    reverse("resourcepool_handler", args=[viewable.id]),
                )
            ],
        )

    def test_POST_create_pool(self):
        name = factory.make_name("name")
        description = factory.make_name("description")
        # Allow the user to edit all resources.
        self.store.allow(self.user.username, ALL_RESOURCES, "edit")
        response = self.client.post(
            reverse("resourcepools_handler"),
            {"name": name, "description": description},
        )
        self.assertEqual(response.status_code, http.client.OK)
        pool = ResourcePool.objects.get(name=name)
        self.assertEqual(pool.description, description)

    def test_POST_create_requires_edit_on_all_resources(self):
        name = factory.make_name("name")
        description = factory.make_name("description")
        response = self.client.post(
            reverse("resourcepools_handler"),
            {"name": name, "description": description},
        )
        self.assertEqual(response.status_code, http.client.FORBIDDEN)
