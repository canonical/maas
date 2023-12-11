# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `VolumeGroup`."""


import random
import uuid

from maasserver.enum import FILESYSTEM_TYPE
from maasserver.forms import (
    CreateLogicalVolumeForm,
    CreateVolumeGroupForm,
    UpdateVolumeGroupForm,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block


class TestCreateVolumeGroupForm(MAASServerTestCase):
    def test_requires_fields(self):
        node = factory.make_Node()
        form = CreateVolumeGroupForm(node, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"name"}, form.errors.keys())

    def test_is_not_valid_if_invalid_uuid(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {
            "name": factory.make_name("name"),
            "uuid": factory.make_string(size=32),
            "block_devices": [block_device.id],
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_missing_block_devices_and_partitions(self):
        node = factory.make_Node()
        vguuid = "%s" % uuid.uuid4()
        data = {"name": factory.make_name("name"), "uuid": vguuid}
        form = CreateVolumeGroupForm(node, data=data)
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
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            "name": factory.make_name("name"),
            "block_devices": [block_device.id],
        }
        form = CreateVolumeGroupForm(node, data=data)
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
        node = factory.make_Node()
        partition = factory.make_Partition()
        data = {
            "name": factory.make_name("name"),
            "partitions": [partition.id],
        }
        form = CreateVolumeGroupForm(node, data=data)
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

    def test_creates_volume_group_with_name_and_uuid(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("vg")
        vguuid = "%s" % uuid.uuid4()
        data = {
            "name": name,
            "uuid": vguuid,
            "block_devices": [block_device.id],
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(name, volume_group.name)
        self.assertEqual(vguuid, volume_group.uuid)

    def test_creates_volume_group_with_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_ids = [block_device.id for block_device in block_devices]
        data = {
            "name": factory.make_name("vg"),
            "block_devices": block_device_ids,
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(block_devices, block_devices_in_vg)

    def test_creates_volume_group_with_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        data = {
            "name": factory.make_name("vg"),
            "block_devices": [boot_disk.id],
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        boot_partition = boot_disk.get_partitiontable().partitions.first()
        self.assertEqual(
            boot_partition.get_effective_filesystem().filesystem_group.id,
            volume_group.id,
        )

    def test_creates_volume_group_with_block_devices_by_name(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_names = [
            block_device.name for block_device in block_devices
        ]
        data = {
            "name": factory.make_name("vg"),
            "block_devices": block_device_names,
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(block_devices, block_devices_in_vg)

    def test_creates_volume_group_with_partitions(self):
        node = factory.make_Node()
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
        data = {"name": factory.make_name("vg"), "partitions": partition_ids}
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(partitions, partitions_in_vg)

    def test_creates_volume_group_with_partitions_by_name(self):
        node = factory.make_Node()
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
        data = {"name": factory.make_name("vg"), "partitions": partition_names}
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(partitions, partitions_in_vg)

    def test_creates_volume_group_with_block_devices_and_partitions(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_ids = [block_device.id for block_device in block_devices]
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
        data = {
            "name": factory.make_name("vg"),
            "block_devices": block_device_ids,
            "partitions": partition_ids,
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
            if filesystem.block_device is not None
        ]
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
            if filesystem.partition is not None
        ]
        self.assertCountEqual(block_devices, block_devices_in_vg)
        self.assertCountEqual(partitions, partitions_in_vg)


class TestUpdateVolumeGroupForm(MAASServerTestCase):
    def test_requires_no_fields(self):
        volume_group = factory.make_VolumeGroup()
        form = UpdateVolumeGroupForm(volume_group, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_name(self):
        volume_group = factory.make_VolumeGroup()
        name = factory.make_name("vg")
        data = {"name": name}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(name, volume_group.name)

    def test_is_not_valid_if_invalid_uuid(self):
        volume_group = factory.make_VolumeGroup()
        data = {"uuid": factory.make_string(size=32)}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_updates_uuid(self):
        volume_group = factory.make_VolumeGroup()
        vguuid = "%s" % uuid.uuid4()
        data = {"uuid": vguuid}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(vguuid, volume_group.uuid)

    def test_adds_block_device(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {"add_block_devices": [block_device.id]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(
            volume_group.id,
            block_device.get_effective_filesystem().filesystem_group.id,
        )

    def test_adds_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node, bootable=True)
        volume_group = factory.make_VolumeGroup(node=node)
        data = {"add_block_devices": [boot_disk.id]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        boot_partition = boot_disk.get_partitiontable().partitions.first()
        self.assertEqual(
            boot_partition.get_effective_filesystem().filesystem_group.id,
            volume_group.id,
        )

    def test_adds_block_device_by_name(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {"add_block_devices": [block_device.name]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(
            volume_group.id,
            block_device.get_effective_filesystem().filesystem_group.id,
        )

    def test_removes_block_device(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=block_device,
            filesystem_group=volume_group,
        )
        data = {"remove_block_devices": [block_device.id]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertIsNone(block_device.get_effective_filesystem())

    def test_removes_block_device_by_name(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=block_device,
            filesystem_group=volume_group,
        )
        data = {"remove_block_devices": [block_device.name]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertIsNone(block_device.get_effective_filesystem())

    def test_adds_partition(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        data = {"add_partitions": [partition.id]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(
            volume_group.id,
            partition.get_effective_filesystem().filesystem_group.id,
        )

    def test_adds_partition_by_name(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        data = {"add_partitions": [partition.name]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEqual(
            volume_group.id,
            partition.get_effective_filesystem().filesystem_group.id,
        )

    def test_removes_partition(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=partition,
            filesystem_group=volume_group,
        )
        data = {"remove_partitions": [partition.id]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertIsNone(partition.get_effective_filesystem())

    def test_removes_partition_by_name(self):
        node = factory.make_Node()
        volume_group = factory.make_VolumeGroup(node=node)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=partition,
            filesystem_group=volume_group,
        )
        data = {"remove_partitions": [partition.name]}
        form = UpdateVolumeGroupForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertIsNone(partition.get_effective_filesystem())


class TestCreateLogicalVolumeForm(MAASServerTestCase):
    def test_requires_no_fields(self):
        volume_group = factory.make_VolumeGroup()
        form = CreateLogicalVolumeForm(volume_group, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"name"}, form.errors.keys())

    def test_is_not_valid_if_invalid_uuid(self):
        volume_group = factory.make_VolumeGroup()
        name = factory.make_name("lv")
        data = {
            "name": name,
            "uuid": factory.make_string(size=32),
            "size": volume_group.get_size() - 1,
        }
        form = CreateLogicalVolumeForm(volume_group, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid uuid."
        )
        self.assertEqual({"uuid": ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_size_less_than_minimum_block_size(self):
        volume_group = factory.make_VolumeGroup()
        name = factory.make_name("lv")
        data = {"name": name, "size": MIN_BLOCK_DEVICE_SIZE - 1}
        form = CreateLogicalVolumeForm(volume_group, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid size."
        )
        self.assertEqual(
            {
                "size": [
                    "Ensure this value is greater than or equal to %s."
                    % MIN_BLOCK_DEVICE_SIZE
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_size_greater_than_free_space(self):
        volume_group = factory.make_VolumeGroup()
        volume_group.create_logical_volume(
            factory.make_name("lv"),
            size=volume_group.get_size() - MIN_BLOCK_DEVICE_SIZE - 1,
        )
        name = factory.make_name("lv")
        free_space = volume_group.get_lvm_free_space()
        data = {"name": name, "size": free_space + 2}
        form = CreateLogicalVolumeForm(volume_group, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an invalid size."
        )
        self.assertEqual(
            {
                "size": [
                    "Ensure this value is less than or equal to %s."
                    % (volume_group.get_lvm_free_space())
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_free_space_less_than_min_size(self):
        volume_group = factory.make_VolumeGroup()
        volume_group.create_logical_volume(
            factory.make_name("lv"), size=volume_group.get_size()
        )
        name = factory.make_name("lv")
        data = {"name": name, "size": MIN_BLOCK_DEVICE_SIZE}
        form = CreateLogicalVolumeForm(volume_group, data=data)
        self.assertFalse(
            form.is_valid(), "Should be invalid because of an no free space."
        )
        self.assertEqual(
            {
                "__all__": [
                    "Volume group (%s) cannot hold any more logical volumes, "
                    "because it doesn't have enough free space."
                    % (volume_group.name)
                ]
            },
            form._errors,
        )

    def test_creates_logical_volume(self):
        volume_group = factory.make_VolumeGroup()
        name = factory.make_name("lv")
        vguuid = "%s" % uuid.uuid4()
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, volume_group.get_size())
        data = {"name": name, "uuid": vguuid, "size": size}
        form = CreateLogicalVolumeForm(volume_group, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        logical_volume = form.save()
        expected_size = round_size_to_nearest_block(
            size, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(logical_volume.name, name)
        self.assertEqual(logical_volume.uuid, vguuid)
        self.assertEqual(logical_volume.size, expected_size)
