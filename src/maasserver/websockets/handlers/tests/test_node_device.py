# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.node_device`"""

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime, HandlerPKError
from maasserver.websockets.handlers.node_device import NodeDeviceHandler


class TestNodeDeviceHandler(MAASServerTestCase):
    def dehydrate_node_device(self, node_device):
        return {
            "id": node_device.id,
            "created": dehydrate_datetime(node_device.created),
            "updated": dehydrate_datetime(node_device.updated),
            "bus": node_device.bus,
            "hardware_type": node_device.hardware_type,
            "vendor_id": node_device.vendor_id,
            "product_id": node_device.product_id,
            "vendor_name": node_device.vendor_name,
            "product_name": node_device.product_name,
            "commissioning_driver": node_device.commissioning_driver,
            "bus_number": node_device.bus_number,
            "device_number": node_device.device_number,
            "pci_address": node_device.pci_address,
            "physical_blockdevice_id": node_device.physical_blockdevice_id,
            "physical_interface_id": node_device.physical_interface_id,
            "numa_node_id": node_device.numa_node_id,
            "node_id": node_device.node_config.node_id,
            "node_config_id": node_device.node_config_id,
        }

    def test_list(self):
        user = factory.make_User()
        handler = NodeDeviceHandler(user, {}, None)
        node = factory.make_Node_with_Interface_on_Subnet()
        factory.make_Node()
        self.assertCountEqual(
            [
                self.dehydrate_node_device(node_device)
                for node_device in node.current_config.nodedevice_set.all()
            ],
            handler.list({"system_id": node.system_id}),
        )

    def test_list_raises_error_if_no_system_id(self):
        user = factory.make_User()
        handler = NodeDeviceHandler(user, {}, None)
        self.assertRaises(HandlerPKError, handler.list, {})
