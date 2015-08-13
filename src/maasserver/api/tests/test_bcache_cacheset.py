# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for bcache cache set API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
import random

from django.core.urlresolvers import reverse
from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_bcache_cache_sets_uri(node):
    """Return a Node's bcache cache sets URI on the API."""
    return reverse(
        'bcache_cache_sets_handler', args=[node.system_id])


def get_bcache_cache_set_uri(cache_set, node=None):
    """Return a bcache cache set URI on the API."""
    if node is None:
        node = cache_set.get_node()
    return reverse(
        'bcache_cache_set_handler', args=[node.system_id, cache_set.id])


class TestBcacheCacheSetsAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            '/api/1.0/nodes/%s/bcache-cache-sets/' % (node.system_id),
            get_bcache_cache_sets_uri(node))

    def test_read(self):
        node = factory.make_Node()
        cache_sets = [
            factory.make_CacheSet(node=node)
            for _ in range(3)
        ]
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            cache_set.id
            for cache_set in cache_sets
            ]
        expected_names = [
            cache_set.name
            for cache_set in cache_sets
            ]
        result_ids = [
            cache_set["id"]
            for cache_set in json.loads(response.content)
            ]
        result_names = [
            cache_set["name"]
            for cache_set in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)
        self.assertItemsEqual(expected_names, result_names)

    def test_create(self):
        node = factory.make_Node(owner=self.logged_in_user)
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {
            'cache_device': cache_device.id,
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.assertEqual(cache_device.id, parsed_device['cache_device']['id'])

    def test_create_403_when_not_owner(self):
        node = factory.make_Node()
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {
            'cache_device': cache_device.id,
        })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_with_missing_cache_fails(self):
        node = factory.make_Node(owner=self.logged_in_user)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {})
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        parsed_content = json.loads(response.content)
        self.assertIn(
            'Either cache_device or cache_partition must be specified.',
            parsed_content['__all__'])


class TestBcacheCacheSetAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            '/api/1.0/nodes/%s/bcache-cache-set/%s/' % (
                node.system_id, cache_set.id),
            get_bcache_cache_set_uri(cache_set, node=node))

    def test_read(self):
        node = factory.make_Node()
        cache_block_device = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=cache_block_device)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_cache_set = json.loads(response.content)
        self.assertThat(parsed_cache_set, ContainsDict({
            "id": Equals(cache_set.id),
            "name": Equals(cache_set.name),
            "resource_uri": Equals(get_bcache_cache_set_uri(cache_set)),
            "cache_device": ContainsDict({
                "id": Equals(cache_block_device.id),
                }),
            }))

    def test_read_404_when_invalid_id(self):
        node = factory.make_Node(owner=self.logged_in_user)
        uri = reverse(
            'bcache_cache_set_handler',
            args=[node.system_id, random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_read_404_when_node_mismatch(self):
        node = factory.make_Node(owner=self.logged_in_user)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set, node=factory.make_Node())
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_deletes_cache_set(self):
        node = factory.make_Node(owner=self.logged_in_user)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(cache_set))

    def test_delete_403_when_not_owner(self):
        cache_set = factory.make_CacheSet()
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_404_when_invalid_id(self):
        node = factory.make_Node(owner=self.logged_in_user)
        uri = reverse(
            'bcache_cache_set_handler',
            args=[node.system_id, random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_400_when_cache_set_in_use(self):
        node = factory.make_Node(owner=self.logged_in_user)
        cache_set = factory.make_CacheSet(node=node)
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set, node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "Cannot delete cache set; it's currently in use.",
            response.content)

    def test_update_change_cache_device(self):
        node = factory.make_Node(owner=self.logged_in_user)
        cache_set = factory.make_CacheSet(node=node)
        new_device = factory.make_PhysicalBlockDevice(node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {
            'cache_device': new_device.id
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.assertEqual(new_device.id, parsed_device['cache_device']['id'])

    def test_update_403_when_not_owner(self):
        cache_set = factory.make_CacheSet()
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_update_400_when_invalid_id(self):
        node = factory.make_Node(owner=self.logged_in_user)
        cache_set = factory.make_CacheSet(node=node)
        new_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(block_device=new_device)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {
            'cache_device': new_device,
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
