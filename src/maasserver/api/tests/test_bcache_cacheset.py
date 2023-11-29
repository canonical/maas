# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import random
from unittest.mock import ANY

from django.urls import reverse

from maasserver.api import bcache_cacheset as bcache_cacheset_module
from maasserver.enum import ENDPOINT, FILESYSTEM_GROUP_TYPE, NODE_STATUS
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from provisioningserver.events import EVENT_TYPES


def get_bcache_cache_sets_uri(node):
    """Return a Node's bcache cache sets URI on the API."""
    return reverse("bcache_cache_sets_handler", args=[node.system_id])


def get_bcache_cache_set_uri(cache_set, node=None):
    """Return a bcache cache set URI on the API."""
    if node is None:
        node = cache_set.get_node()
    return reverse(
        "bcache_cache_set_handler", args=[node.system_id, cache_set.id]
    )


class TestBcacheCacheSetsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/bcache-cache-sets/" % (node.system_id),
            get_bcache_cache_sets_uri(node),
        )

    def test_read(self):
        node = factory.make_Node()
        cache_sets = [factory.make_CacheSet(node=node) for _ in range(3)]
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [cache_set.id for cache_set in cache_sets]
        expected_names = [cache_set.name for cache_set in cache_sets]
        result_ids = [
            cache_set["id"] for cache_set in json_load_bytes(response.content)
        ]
        result_names = [
            cache_set["name"]
            for cache_set in json_load_bytes(response.content)
        ]
        self.assertCountEqual(expected_ids, result_ids)
        self.assertCountEqual(expected_names, result_names)

    def test_create(self):
        mock_create_audit_event = self.patch(
            bcache_cacheset_module, "create_audit_event"
        )
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {"cache_device": cache_device.id})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(cache_device.id, parsed_device["cache_device"]["id"])
        mock_create_audit_event.assert_called_once_with(
            EVENT_TYPES.NODE,
            ENDPOINT.API,
            ANY,
            node.system_id,
            "Created bcache cache set.",
        )

    def test_create_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {"cache_device": cache_device.id})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        cache_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {"cache_device": cache_device.id})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_create_with_missing_cache_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uri = get_bcache_cache_sets_uri(node)
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        parsed_content = json_load_bytes(response.content)
        self.assertIn(
            "Either cache_device or cache_partition must be specified.",
            parsed_content["__all__"],
        )


class TestBcacheCacheSetAPI(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/bcache-cache-set/%s/"
            % (node.system_id, cache_set.id),
            get_bcache_cache_set_uri(cache_set, node=node),
        )

    def test_read(self):
        node = factory.make_Node()
        cache_block_device = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=cache_block_device)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_cache_set = json_load_bytes(response.content)
        self.assertEqual(parsed_cache_set.get("id"), cache_set.id)
        self.assertEqual(parsed_cache_set.get("name"), cache_set.name)
        self.assertEqual(
            parsed_cache_set.get("resource_uri"),
            get_bcache_cache_set_uri(cache_set),
        )
        self.assertEqual(
            parsed_cache_set.get("cache_device", {}).get("id"),
            cache_block_device.id,
        )

        self.assertEqual(
            parsed_cache_set.get("system_id"), cache_set.get_node().system_id
        )

    def test_read_404_when_invalid_id(self):
        node = factory.make_Node(owner=self.user)
        uri = reverse(
            "bcache_cache_set_handler",
            args=[node.system_id, random.randint(100, 1000)],
        )
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_read_404_when_node_mismatch(self):
        node = factory.make_Node(owner=self.user)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set, node=factory.make_Node())
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_deletes_cache_set(self):
        mock_create_audit_event = self.patch(
            bcache_cacheset_module, "create_audit_event"
        )
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(cache_set))
        mock_create_audit_event.assert_called_once_with(
            EVENT_TYPES.NODE,
            ENDPOINT.API,
            ANY,
            node.system_id,
            "Deleted bcache cache set.",
        )

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uri = reverse(
            "bcache_cache_set_handler",
            args=[node.system_id, random.randint(100, 1000)],
        )
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_delete_400_when_cache_set_in_use(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_set = factory.make_CacheSet(node=node)
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set,
            node=node,
        )
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b"Cannot delete cache set; it's currently in use.",
            response.content,
        )

    def test_update_change_cache_device(self):
        mock_create_audit_event = self.patch(
            bcache_cacheset_module, "create_audit_event"
        )
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_set = factory.make_CacheSet(node=node)
        new_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {"cache_device": new_device.id})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(new_device.id, parsed_device["cache_device"]["id"])
        mock_create_audit_event.assert_called_once_with(
            EVENT_TYPES.NODE,
            ENDPOINT.API,
            ANY,
            node.system_id,
            "Updated bcache cache set.",
        )

    def test_update_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        cache_set = factory.make_CacheSet(node=node)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_update_400_when_invalid_id(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        cache_set = factory.make_CacheSet(node=node)
        new_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(block_device=new_device)
        uri = get_bcache_cache_set_uri(cache_set)
        response = self.client.put(uri, {"cache_device": new_device})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
