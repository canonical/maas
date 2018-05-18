# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for resource pools API."""

import http.client
import json
from operator import attrgetter

from django.conf import settings
from maasserver.models import ResourcePool
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.django_urls import reverse


class TestResourcePoolsAPI(APITestCase.ForUser):

    def test_handler_path(self):
        self.assertEqual(
            '/MAAS/api/2.0/resourcepools/', reverse('resourcepools_handler'))

    def test_create_pool(self):
        self.become_admin()
        name = factory.make_name('name')
        description = factory.make_name('description')
        response = self.client.post(
            reverse('resourcepools_handler'),
            {'name': name, 'description': description})
        self.assertEqual(response.status_code, http.client.OK)
        pool = ResourcePool.objects.get(name=name)
        self.assertEqual(pool.description, description)

    def test_create_requires_admin(self):
        name = factory.make_name('name')
        description = factory.make_name('description')
        response = self.client.post(
            reverse('resourcepools_handler'),
            {'name': name, 'description': description})
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_list_returns_pools_list(self):
        pools = [factory.make_ResourcePool() for _ in range(3)]
        # include the default pool
        pools.append(ResourcePool.objects.get_default_resource_pool())
        pools.sort(key=attrgetter('name'))
        response = self.client.get(reverse('resourcepools_handler'), {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertItemsEqual(
            [(pool['name'], pool['description'], pool['resource_uri'])
             for pool in result],
            [(
                pool.name,
                pool.description,
                reverse('resourcepool_handler', args=[pool.id]))
             for pool in pools])
