# Copyright 2014-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.core.exceptions import ValidationError

from maasserver.models import PhysicalBlockDevice
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPhysicalBlockDeviceManager(MAASServerTestCase):
    def test_model_serial_and_no_id_path_requirements_should_save(self):
        node = factory.make_Node()
        blockdevice = PhysicalBlockDevice(
            node=node,
            name="sda",
            block_size=512,
            size=MIN_BLOCK_DEVICE_SIZE,
            model="A2M0003",
            serial="001",
        )
        # Should work without issue
        blockdevice.save()

    def test_id_path_and_no_model_serial_requirements_should_save(self):
        node = factory.make_Node()
        blockdevice = PhysicalBlockDevice(
            node=node,
            name="sda",
            block_size=512,
            size=MIN_BLOCK_DEVICE_SIZE,
            id_path="/dev/disk/by-id/A2M0003-001",
        )
        # Should work without issue
        blockdevice.save()

    def test_no_id_path_and_no_serial(self):
        node = factory.make_Node()
        blockdevice = PhysicalBlockDevice(
            node=node,
            name="sda",
            block_size=512,
            size=MIN_BLOCK_DEVICE_SIZE,
            model="A2M0003",
        )
        self.assertRaises(ValidationError, blockdevice.save)

    def test_no_id_path_and_no_model(self):
        node = factory.make_Node()
        blockdevice = PhysicalBlockDevice(
            node=node,
            name="sda",
            block_size=512,
            size=MIN_BLOCK_DEVICE_SIZE,
            serial="001",
        )
        self.assertRaises(ValidationError, blockdevice.save)

    def test_default_numa_node_from_node(self):
        node = factory.make_Node()
        bdev = PhysicalBlockDevice.objects.create(
            serial="123",
            model="disk",
            name="sda",
            size=MIN_BLOCK_DEVICE_SIZE,
            block_size=1024,
            node=node,
        )
        self.assertEqual(bdev.numa_node, node.default_numanode)

    def test_node_from_numa_node(self):
        numa_node = factory.make_NUMANode()
        bdev = PhysicalBlockDevice.objects.create(
            serial="123",
            model="disk",
            name="sda",
            size=MIN_BLOCK_DEVICE_SIZE,
            block_size=1024,
            numa_node=numa_node,
        )
        self.assertEqual(bdev.node, numa_node.node)

    def test_node_and_numa_node_fail(self):
        node = factory.make_Node()
        numa_node = factory.make_NUMANode()
        self.assertRaises(
            ValidationError,
            PhysicalBlockDevice.objects.create,
            serial="123",
            model="disk",
            name="sda",
            size=MIN_BLOCK_DEVICE_SIZE,
            block_size=1024,
            node=node,
            numa_node=numa_node,
        )

    def test_serialize(self):
        block_device = factory.make_PhysicalBlockDevice()
        self.assertEqual(
            {
                "id": block_device.id,
                "name": block_device.name,
                "id_path": block_device.id_path,
                "model": block_device.model,
                "serial": block_device.serial,
            },
            block_device.serialize(),
        )
