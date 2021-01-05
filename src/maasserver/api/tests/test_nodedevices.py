# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the node devices API."""
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
    """Tests for /api/2.0/nodes/<system_id>/devices/."""

    @staticmethod
    def get_script_results_uri(node):
        """Return the script's URI on the API."""
        return reverse("node_devices_handler", args=[node.system_id])

    def test_hander_path(self):
        node = factory.make_Node()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/devices/" % node.system_id,
            self.get_script_results_uri(node),
        )

    def test_GET(self):
        node = factory.make_Node()

        response = self.client.get(self.get_script_results_uri(node))
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [node_device.id for node_device in node.node_devices.all()],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_bus(self):
        node = factory.make_Node()
        bus = factory.pick_choice(NODE_DEVICE_BUS_CHOICES)

        response = self.client.get(
            self.get_script_results_uri(node), {"bus": bus}
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [
                node_device.id
                for node_device in node.node_devices.filter(bus=bus)
            ],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_hardware_type(self):
        node = factory.make_Node()
        hardware_type = factory.pick_choice(HARDWARE_TYPE_CHOICES)

        response = self.client.get(
            self.get_script_results_uri(node), {"hardware_type": hardware_type}
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [
                node_device.id
                for node_device in node.node_devices.filter(
                    hardware_type=hardware_type
                )
            ],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_vendor_id(self):
        node = factory.make_Node()
        vendor_id = factory.make_hex_string(4)
        node_devices = [
            factory.make_NodeDevice(node=node, vendor_id=vendor_id)
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_results_uri(node), {"vendor_id": vendor_id}
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [node_device.id for node_device in node_devices],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_product_id(self):
        node = factory.make_Node()
        product_id = factory.make_hex_string(4)
        node_devices = [
            factory.make_NodeDevice(node=node, product_id=product_id)
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_results_uri(node), {"product_id": product_id}
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [node_device.id for node_device in node_devices],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_vendor_name(self):
        node = factory.make_Node()
        vendor_name = factory.make_name("vendor_name")
        node_devices = [
            factory.make_NodeDevice(node=node, vendor_name=vendor_name)
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_results_uri(node), {"vendor_name": vendor_name}
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [node_device.id for node_device in node_devices],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_product_name(self):
        node = factory.make_Node()
        product_name = factory.make_name("product_name")
        node_devices = [
            factory.make_NodeDevice(node=node, product_name=product_name)
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_results_uri(node), {"product_name": product_name}
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [node_device.id for node_device in node_devices],
            [node_device["id"] for node_device in parsed_results],
        )

    def test_GET_filter_commissioning_driver(self):
        node = factory.make_Node()
        commissioning_driver = factory.make_name("commissioning_driver")
        node_devices = [
            factory.make_NodeDevice(
                node=node, commissioning_driver=commissioning_driver
            )
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_results_uri(node),
            {"commissioning_driver": commissioning_driver},
        )
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertEqual(
            [node_device.id for node_device in node_devices],
            [node_device["id"] for node_device in parsed_results],
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
            id = "%s:%s" % (node_device.bus_number, node_device.device_number)
        return reverse(
            "node_device_handler", args=[node_device.node.system_id, id]
        )

    def test_hander_path(self):
        node_device = factory.make_NodeDevice()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/devices/%s/"
            % (node_device.node.system_id, node_device.id),
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
                "system_id": node_device.node.system_id,
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
