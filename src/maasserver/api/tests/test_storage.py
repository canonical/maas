# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for storage API."""

__all__ = []

import http.client

from django.core.urlresolvers import reverse
from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


class TestStoragesAPI(APITestCase.ForUser):

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/storages/', reverse('storages_handler'))

    def create_storages(self, owner, nb=3):
        return [
            factory.make_Node(
                interface=True, node_type=NODE_TYPE.STORAGE, owner=owner)
            for _ in range(nb)
        ]

    def test_read_lists_storage(self):
        # The api allows for fetching the list of storages.
        storages = self.create_storages(owner=self.user)
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse('storages_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [storage.system_id for storage in storages],
            [storage.get('system_id') for storage in parsed_result])

    def test_read_ignores_nodes(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse('storages_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [],
            [storage.get('system_id') for storage in parsed_result])

    def test_read_with_id_returns_matching_storage(self):
        # The "list" operation takes optional "id" parameters.  Only
        # storages with matching ids will be returned.
        storages = self.create_storages(owner=self.user)
        ids = [storage.system_id for storage in storages]
        matching_id = ids[0]
        response = self.client.get(reverse('storages_handler'), {
            'id': [matching_id],
        })
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [matching_id],
            [storage.get('system_id') for storage in parsed_result])

    def test_read_returns_limited_fields(self):
        self.create_storages(owner=self.user)
        response = self.client.get(reverse('storages_handler'))
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'system_id',
                'storage_type',
                'node_type',
                'node_type_name',
                'resource_uri',
            ],
            list(parsed_result[0]))


def get_storage_uri(storage):
    """Return a storage's URI on the API."""
    return reverse('storage_handler', args=[storage.system_id])


class TestStorageAPI(APITestCase.ForUser):

    def test_handler_path(self):
        system_id = factory.make_name('system-id')
        self.assertEqual(
            '/api/2.0/storages/%s/' % system_id,
            reverse('storage_handler', args=[system_id]))

    def test_GET_reads_storage(self):
        storage = factory.make_Node(
            node_type=NODE_TYPE.STORAGE, owner=self.user)

        response = self.client.get(get_storage_uri(storage))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_storage = json_load_bytes(response.content)
        self.assertEqual(storage.system_id, parsed_storage["system_id"])

    def test_DELETE_removes_storage(self):
        self.become_admin()
        storage = factory.make_Node(
            node_type=NODE_TYPE.STORAGE, owner=self.user)
        response = self.client.delete(get_storage_uri(storage))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(storage))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        storage = factory.make_Node(
            node_type=NODE_TYPE.STORAGE, owner=factory.make_User())
        response = self.client.delete(get_storage_uri(storage))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(storage, reload_object(storage))
