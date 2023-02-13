# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client

from django.urls import reverse

from maasserver.enum import NODE_DEVICE_BUS_CHOICES
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.matchers import HasStatusCode
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from metadataserver.enum import HARDWARE_TYPE_CHOICES


class TestNodeDevicesAPI(APITestCase.ForUser):
    def test_hander_path(self):
        node = factory.make_Node()
        self.assertEqual(
            reverse("node_devices_handler", args=[node.system_id]),
            f"/MAAS/api/2.0/nodes/{node.system_id}/devices/",
        )

    def test_GET(self):
        node = factory.make_Node()
        node_devices = [
            factory.make_NodeDevice(node=node),
            factory.make_NodeDevice(node=node),
        ]
        response = self.client.get(
            f"/MAAS/api/2.0/nodes/{node.system_id}/devices/",
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertCountEqual(
            [node_device.id for node_device in node_devices],
            [node_device["id"] for node_device in response.json()],
        )


class TestNodeDevicesAPIFilter(APITestCase.ForUser):
    scenarios = [
        ("filter=bus", {"choices": NODE_DEVICE_BUS_CHOICES, "key": "bus"}),
        (
            "filter=hardware_type",
            {"choices": HARDWARE_TYPE_CHOICES, "key": "hardware_type"},
        ),
        (
            "filter=vendor_id",
            {
                "choices": lambda: factory.make_hex_string(4),
                "key": "vendor_id",
            },
        ),
        (
            "filter=product_id",
            {
                "choices": lambda: factory.make_hex_string(4),
                "key": "product_id",
            },
        ),
        (
            "filter=vendor_name",
            {"choices": factory.make_name, "key": "vendor_name"},
        ),
        (
            "filter=product_name",
            {"choices": factory.make_name, "key": "product_name"},
        ),
        (
            "filter=commissioning_driver",
            {"choices": factory.make_name, "key": "commissioning_driver"},
        ),
    ]

    def setUp(self):
        super().setUp()
        self.node = factory.make_Node()
        self.uri = reverse("node_devices_handler", args=[self.node.system_id])

    def test_GET_filter(self):
        if callable(self.choices):
            choice1 = self.choices()
        else:
            choice1 = factory.pick_choice(self.choices)
        node_device = factory.make_NodeDevice(
            node=self.node, **{self.key: choice1}
        )
        # create a device with different criteria
        if callable(self.choices):
            choice2 = self.choices()
        else:
            choice2 = factory.pick_choice(self.choices, but_not=[choice1])
        factory.make_NodeDevice(node=self.node, **{self.key: choice2})

        response = self.client.get(self.uri, {self.key: choice1})
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            [node_device.id],
            [node_device["id"] for node_device in response.json()],
        )


class TestNodeDeviceAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<system_id>/device/<id>."""

    def get_node_device_uri(self, node_device, force_id=False):
        """Return the script's URI on the API."""
        if force_id or factory.pick_bool():
            id = node_device.id
        elif node_device.is_pcie:
            id = node_device.pci_address
        elif node_device.is_usb:
            id = f"{node_device.bus_number}:{node_device.device_number}"
        return reverse(
            "node_device_handler",
            args=[node_device.node_config.node.system_id, id],
        )

    def test_hander_path(self):
        node_device = factory.make_NodeDevice()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/"
            f"{node_device.node_config.node.system_id}/devices/{node_device.id}/",
            self.get_node_device_uri(node_device, True),
        )

    def test_GET(self):
        node_device = factory.make_NodeDevice()

        response = self.client.get(self.get_node_device_uri(node_device))
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(
            {
                "id": node_device.id,
                "bus": node_device.bus,
                "bus_name": node_device.get_bus_display(),
                "hardware_type": node_device.hardware_type,
                "hardware_type_name": node_device.get_hardware_type_display(),
                "system_id": node_device.node_config.node.system_id,
                "numa_node": node_device.numa_node.index,
                "physical_blockdevice": None,
                "physical_interface": None,
                "vendor_id": node_device.vendor_id,
                "product_id": node_device.product_id,
                "vendor_name": node_device.vendor_name,
                "product_name": node_device.product_name,
                "commissioning_driver": node_device.commissioning_driver,
                "bus_number": node_device.bus_number,
                "device_number": node_device.device_number,
                "pci_address": node_device.pci_address,
                "resource_uri": self.get_node_device_uri(node_device, True),
            },
            parsed_result,
        )

    def test_DELETE(self):
        self.become_admin()
        node_device = factory.make_NodeDevice()

        response = self.client.delete(self.get_node_device_uri(node_device))
        self.assertThat(response, HasStatusCode(http.client.NO_CONTENT))
        self.assertIsNone(reload_object(node_device))

    def test_DELETE_admin_only(self):
        node_device = factory.make_NodeDevice()

        response = self.client.delete(self.get_node_device_uri(node_device))
        self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))
        self.assertIsNotNone(reload_object(node_device))
