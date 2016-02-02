# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for devices API."""

__all__ = []

import http.client
import random

from django.core.urlresolvers import reverse
from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import Device
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.utils.converters import json_load_bytes


class TestDevicesAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/devices/', reverse('devices_handler'))

    def test_POST_creates_device(self):
        hostname = factory.make_name('host')
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse('devices_handler'),
            {
                'hostname': hostname,
                'mac_addresses': macs,
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        system_id = json_load_bytes(response.content)['system_id']
        device = Device.objects.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertIsNone(device.parent)
        self.assertEquals(device.node_type, NODE_TYPE.DEVICE)
        self.assertEquals(self.logged_in_user, device.owner)
        self.assertEquals(
            macs,
            {nic.mac_address for nic in device.interface_set.all()})

    def test_POST_creates_device_with_parent(self):
        parent = factory.make_Node()
        hostname = factory.make_name('host')
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse('devices_handler'),
            {
                'hostname': hostname,
                'mac_addresses': macs,
                'parent': parent.system_id,
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        system_id = json_load_bytes(response.content)['system_id']
        device = Device.objects.get(system_id=system_id)
        self.assertEquals(hostname, device.hostname)
        self.assertEquals(parent, device.parent)
        self.assertEqual(device.node_type, NODE_TYPE.DEVICE)

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse('devices_handler'),
            {
                'hostname': factory.make_string(),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'parent',
                'tag_names',
                'ip_addresses',
                'resource_uri',
                'zone',
            ],
            list(parsed_result))

    def create_devices(self, owner, nb=3):
        return [
            factory.make_Node(
                interface=True, node_type=NODE_TYPE.DEVICE, owner=owner)
            for _ in range(nb)
        ]

    def test_read_lists_devices(self):
        # The api allows for fetching the list of devices.
        devices = self.create_devices(owner=self.logged_in_user)
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [device.system_id for device in devices],
            [device.get('system_id') for device in parsed_result])

    def test_read_ignores_nodes(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [],
            [device.get('system_id') for device in parsed_result])

    def test_read_with_id_returns_matching_devices(self):
        # The "list" operation takes optional "id" parameters.  Only
        # devices with matching ids will be returned.
        devices = self.create_devices(owner=self.logged_in_user)
        ids = [device.system_id for device in devices]
        matching_id = ids[0]
        response = self.client.get(reverse('devices_handler'), {
            'id': [matching_id],
        })
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [matching_id],
            [device.get('system_id') for device in parsed_result])

    def test_read_with_macaddress_returns_matching_devices(self):
        # The "list" operation takes optional "mac_address" parameters.  Only
        # devices with matching MAC addresses will be returned.
        devices = self.create_devices(owner=self.logged_in_user)
        matching_device = devices[0]
        matching_mac = matching_device.get_boot_interface().mac_address
        response = self.client.get(reverse('devices_handler'), {
            'mac_address': [matching_mac],
        })
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [matching_device.system_id],
            [device.get('system_id') for device in parsed_result])

    def test_read_returns_limited_fields(self):
        self.create_devices(owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'))
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'parent',
                'tag_names',
                'ip_addresses',
                'resource_uri',
                'zone',
            ],
            list(parsed_result[0]))


def get_device_uri(device):
    """Return a device's URI on the API."""
    return reverse('device_handler', args=[device.system_id])


class TestDeviceAPI(APITestCase):

    def test_handler_path(self):
        system_id = factory.make_name('system-id')
        self.assertEqual(
            '/api/2.0/devices/%s/' % system_id,
            reverse('device_handler', args=[system_id]))

    def test_POST_method_doesnt_exist(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=self.logged_in_user)

        response = self.client.post(get_device_uri(device))
        self.assertEqual(
            http.client.METHOD_NOT_ALLOWED, response.status_code,
            response.content)

    def test_GET_reads_device(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=self.logged_in_user)

        response = self.client.get(get_device_uri(device))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(device.system_id, parsed_device["system_id"])

    def test_PUT_updates_device_hostname(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=self.logged_in_user)
        new_hostname = factory.make_name('hostname')

        response = self.client.put(
            get_device_uri(device), {'hostname': new_hostname})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_hostname, device.hostname)

    def test_PUT_updates_device_parent(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=self.logged_in_user,
            parent=parent)
        new_parent = factory.make_Node()

        response = self.client.put(
            get_device_uri(device), {'parent': new_parent.system_id})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_parent, device.parent)

    def test_PUT_rejects_edit_if_not_permitted(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=factory.make_User())
        old_hostname = device.hostname

        response = self.client.put(
            get_device_uri(device),
            {'hostname': factory.make_name('hostname')})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(old_hostname, reload_object(device).hostname)

    def test_DELETE_removes_device(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=self.logged_in_user)
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(device))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        device = factory.make_Node(
            node_type=NODE_TYPE.DEVICE, owner=factory.make_User())
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(device, reload_object(device))
