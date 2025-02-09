# Copyright 2019-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `VMFS`."""

import random
import uuid

from maasserver.enum import FILESYSTEM_TYPE
from maasserver.forms import CreateVMFSForm, UpdateVMFSForm
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.storage_layouts import VMFS6StorageLayout, VMFS7StorageLayout
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.test_storage_layouts import LARGE_BLOCK_DEVICE


def make_Node_with_VMFS_layout(*args, **kwargs):
    """Create a node with the VMFS storage layout applied."""
    kwargs["with_boot_disk"] = False
    node = factory.make_Node(*args, **kwargs)
    factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
    layout_class = random.choice([VMFS6StorageLayout, VMFS7StorageLayout])
    layout = layout_class(node)
    layout.configure()
    return node


class TestCreateVMFSForm(MAASServerTestCase):
    def test_requires_fields(self):
        node = make_Node_with_VMFS_layout()
        form = CreateVMFSForm(node, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"name"}, form.errors.keys())

    def test_is_not_valid_if_invalid_uuid(self):
        node = make_Node_with_VMFS_layout()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {
            "name": factory.make_name("name"),
            "uuid": factory.make_string(size=32),
            "block_devices": [block_device.id],
        }
        form = CreateVMFSForm(node, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_missing_block_devices_and_partitions(self):
        node = make_Node_with_VMFS_layout()
        data = {"name": factory.make_name("name"), "uuid": uuid.uuid4()}
        form = CreateVMFSForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of missing block_devices and "
            "partitions.",
        )
        self.assertEqual(
            {
                "__all__": [
                    "At least one valid block device or partition is required."
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_block_device_does_not_belong_to_node(self):
        node = make_Node_with_VMFS_layout()
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            "name": factory.make_name("name"),
            "block_devices": [block_device.id],
        }
        form = CreateVMFSForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of block device does not "
            "belonging to node.",
        )
        self.assertEqual(
            {
                "block_devices": [
                    "Select a valid choice. %s is not one of the available "
                    "choices." % block_device.id
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_partition_does_not_belong_to_node(self):
        node = make_Node_with_VMFS_layout()
        partition = factory.make_Partition()
        data = {
            "name": factory.make_name("name"),
            "partitions": [partition.id],
        }
        form = CreateVMFSForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of partition does not "
            "belonging to node.",
        )
        self.assertEqual(
            {
                "partitions": [
                    "Select a valid choice. %s is not one of the available "
                    "choices." % partition.id
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_vmfs_layout_is_not_applied(self):
        node = factory.make_Node(with_boot_disk=False)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {
            "name": factory.make_name("name"),
            "block_devices": [block_device.id],
        }
        form = CreateVMFSForm(node, data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("VMFS", form.errors)

    def test_creates_volume_group_with_block_devices(self):
        node = make_Node_with_VMFS_layout()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_ids = [block_device.id for block_device in block_devices]
        data = {
            "name": factory.make_name("name"),
            "block_devices": block_device_ids,
        }
        form = CreateVMFSForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertCountEqual(
            block_device_ids,
            [
                fs.partition.partition_table.block_device_id
                for fs in vmfs.filesystems.all()
            ],
        )

    def test_creates_with_block_devices_by_name(self):
        node = make_Node_with_VMFS_layout()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_names = [
            block_device.name for block_device in block_devices
        ]
        data = {
            "name": factory.make_name("name"),
            "block_devices": block_device_names,
        }
        form = CreateVMFSForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertCountEqual(
            [block_device.id for block_device in block_devices],
            [
                fs.partition.partition_table.block_device_id
                for fs in vmfs.filesystems.all()
            ],
        )

    def test_creates_with_partitions(self):
        node = make_Node_with_VMFS_layout()
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_BLOCK_DEVICE_SIZE * 3) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        partition_ids = [partition.id for partition in partitions]
        data = {"name": factory.make_name("name"), "partitions": partition_ids}
        form = CreateVMFSForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertCountEqual(
            partition_ids,
            [fs.partition_id for fs in vmfs.filesystems.all()],
        )

    def test_creates_with_partitions_by_name(self):
        node = make_Node_with_VMFS_layout()
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_BLOCK_DEVICE_SIZE * 3) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        partition_names = [partition.name for partition in partitions]
        data = {
            "name": factory.make_name("name"),
            "partitions": partition_names,
        }
        form = CreateVMFSForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(partitions, partitions_in_vg)


class TestUpdateVMFSForm(MAASServerTestCase):
    def test_requires_no_fields(self):
        vmfs = factory.make_VMFS()
        form = UpdateVMFSForm(vmfs, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_name(self):
        vmfs = factory.make_VMFS()
        name = factory.make_name("name")
        form = UpdateVMFSForm(vmfs, data={"name": name})
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertEqual(name, vmfs.name)

    def test_is_not_valid_if_invalid_uuid(self):
        vmfs = factory.make_VMFS()
        form = UpdateVMFSForm(vmfs, data={"uuid": factory.make_string(32)})
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_updates_uuid(self):
        vmfs = factory.make_VMFS()
        new_uuid = str(uuid.uuid4())
        form = UpdateVMFSForm(vmfs, data={"uuid": new_uuid})
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertEqual(new_uuid, vmfs.uuid)

    def test_adds_block_device(self):
        node = make_Node_with_VMFS_layout()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {"add_block_devices": [block_device.id]}
        form = UpdateVMFSForm(vmfs, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        part = block_device.get_partitiontable().partitions.first()
        self.assertEqual(
            vmfs.id, part.get_effective_filesystem().filesystem_group_id
        )

    def test_adds_block_device_by_name(self):
        node = make_Node_with_VMFS_layout()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {"add_block_devices": [block_device.name]}
        form = UpdateVMFSForm(vmfs, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        part = block_device.get_partitiontable().partitions.first()
        self.assertEqual(
            vmfs.id, part.get_effective_filesystem().filesystem_group_id
        )

    def test_adds_partition(self):
        node = make_Node_with_VMFS_layout()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        data = {"add_partitions": [partition.id]}
        form = UpdateVMFSForm(vmfs, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertEqual(
            vmfs.id, partition.get_effective_filesystem().filesystem_group.id
        )

    def test_adds_partition_by_name(self):
        node = make_Node_with_VMFS_layout()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        data = {"add_partitions": [partition.name]}
        form = UpdateVMFSForm(vmfs, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertEqual(
            vmfs.id, partition.get_effective_filesystem().filesystem_group.id
        )

    def test_removes_partition(self):
        node = make_Node_with_VMFS_layout()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=partition,
            filesystem_group=vmfs,
        )
        data = {"remove_partitions": [partition.id]}
        form = UpdateVMFSForm(vmfs, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertIsNone(partition.get_effective_filesystem())

    def test_removes_partition_by_name(self):
        node = make_Node_with_VMFS_layout()
        vmfs = factory.make_VMFS(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=partition,
            filesystem_group=vmfs,
        )
        data = {"remove_partitions": [partition.name]}
        form = UpdateVMFSForm(vmfs, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        vmfs = form.save()
        self.assertIsNone(partition.get_effective_filesystem())
