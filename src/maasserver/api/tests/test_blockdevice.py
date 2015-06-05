# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for blockdevice API."""

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

from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object


def get_blockdevices_uri(node):
    """Return a Node's BlockDevice URI on the API."""
    return reverse(
        'blockdevices_handler', args=[node.system_id])


def get_blockdevice_uri(device, node=None):
    """Return a BlockDevice's URI on the API."""
    if node is None:
        node = device.node
    return reverse(
        'blockdevice_handler', args=[node.system_id, device.id])


class TestBlockDevices(APITestCase):

    def test_read(self):
        node = factory.make_Node()
        devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
            ]
        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        # Ensure the response status is OK
        self.assertEqual(httplib.OK, response.status_code, response.content)

        # Ensure all the device ids match.
        expected_device_ids = [
            device.id
            for device in devices
            ]
        result_device_ids = [
            device["id"]
            for device in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_device_ids, result_device_ids)


class TestBlockDeviceAPI(APITestCase):

    def test_read(self):
        device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(device)
        response = self.client.get(uri)

        # Ensure the response status is OK
        self.assertEqual(httplib.OK, response.status_code, response.content)

        parsed_device = json.loads(response.content)
        self.assertEquals(device.id, parsed_device["id"])
        self.assertEquals(device.type, parsed_device["type"])

    def test_add_tag_returns_403_for_non_admin(self):
        device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(device)
        response = self.client.get(
            uri, {'op': 'add_tag', 'tag': factory.make_name('tag')})

        # Ensure the response status is FORBIDDEN
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_add_tag_to_block_device(self):
        self.become_admin()
        device = factory.make_PhysicalBlockDevice()
        tag_to_be_added = factory.make_name('tag')
        uri = get_blockdevice_uri(device)
        response = self.client.get(
            uri, {'op': 'add_tag', 'tag': tag_to_be_added})

        # Ensure the response status is OK
        self.assertEqual(httplib.OK, response.status_code, response.content)

        # Ensure the change was persisted
        device = reload_object(device)
        self.assertIn(tag_to_be_added, device.tags)

        # Check whether the returned data reflects the change
        parsed_device = json.loads(response.content)
        self.assertIn(tag_to_be_added, parsed_device['tags'])

    def test_add_tag_returns_404_when_system_id_doesnt_match(self):
        self.become_admin()
        device = factory.make_PhysicalBlockDevice()
        other_node = factory.make_Node()
        uri = get_blockdevice_uri(device, node=other_node)
        response = self.client.get(
            uri, {'op': 'add_tag', 'tag': factory.make_name('tag')})

        # Ensure the response status is NOT_FOUND.
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_remove_tag_returns_403_for_non_admin(self):
        device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(device)
        response = self.client.get(
            uri, {'op': 'remove_tag', 'tag': factory.make_name('tag')})

        # Ensure the response status is FORBIDDEN
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_remove_tag_from_block_device(self):
        self.become_admin()
        device = factory.make_PhysicalBlockDevice()
        tag_to_be_removed = device.tags[0]
        uri = get_blockdevice_uri(device)
        response = self.client.get(
            uri, {'op': 'remove_tag', 'tag': tag_to_be_removed})

        # Ensure the response status is OK
        self.assertEqual(httplib.OK, response.status_code, response.content)

        # Ensure the change was persisted
        device = reload_object(device)
        self.assertNotIn(tag_to_be_removed, device.tags)

        # Check whether the returned data reflects the change
        parsed_device = json.loads(response.content)
        self.assertNotIn(tag_to_be_removed, parsed_device['tags'])
