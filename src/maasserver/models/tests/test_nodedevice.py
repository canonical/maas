# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from django.core.exceptions import ValidationError

from maasserver.enum import NODE_DEVICE_BUS
from maasserver.models import NodeDevice
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestNodeDevice(MAASServerTestCase):
    def test_save_fills_in_bus_dev_num_for_pcie(self):
        bus_number = random.randint(0, 2 ** 16)
        device_number = random.randint(0, 2 ** 16)
        node = factory.make_Node()
        node_device = NodeDevice.objects.create(
            bus=NODE_DEVICE_BUS.PCIE,
            node=node,
            numa_node=random.choice(node.numanode_set.all()),
            vendor_id=factory.make_hex_string(size=4),
            product_id=factory.make_hex_string(size=4),
            pci_address=(
                f"{hex(bus_number)[2:].zfill(2)}:"
                f"{hex(device_number)[2:].zfill(2)}.0"
            ),
        )
        self.assertEqual(bus_number, node_device.bus_number)
        self.assertEqual(device_number, node_device.device_number)

    def test_save_validates_no_pci_address_on_usb(self):
        node_device = factory.make_NodeDevice(bus=NODE_DEVICE_BUS.PCIE)
        node_device.bus = NODE_DEVICE_BUS.USB
        self.assertRaises(ValidationError, node_device.save)
