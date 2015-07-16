# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `VolumeGroup`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import uuid

from maasserver.forms import CreateVolumeGroupForm
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCreateVolumeGroupForm(MAASServerTestCase):

    def test_requires_fields(self):
        node = factory.make_Node()
        form = CreateVolumeGroupForm(node, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['name'], form.errors.keys())

    def test_is_not_valid_if_invalid_uuid(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        data = {
            'name': factory.make_name("name"),
            'uuid': factory.make_string(size=32),
            'block_devices': [block_device.id],
            }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid uuid.")
        self.assertEquals({'uuid': ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_missing_block_devices_and_partitions(self):
        node = factory.make_Node()
        vguuid = "%s" % uuid.uuid4()
        data = {
            'name': factory.make_name("name"),
            'uuid': vguuid,
            }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of missing block_devices and "
            "partitions.")
        self.assertEquals({
            '__all__': [
                "Atleast one valid block device or partition is required.",
                ]}, form._errors)

    def test_is_not_valid_if_block_device_does_not_belong_to_node(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'name': factory.make_name("name"),
            'block_devices': [block_device.id],
            }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of block device does not "
            "belonging to node.")
        self.assertEquals({
            'block_devices': [
                "Select a valid choice. %s is not one of the available "
                "choices." % block_device.id,
                ]}, form._errors)

    def test_is_not_valid_if_partition_does_not_belong_to_node(self):
        node = factory.make_Node()
        partition = factory.make_Partition()
        data = {
            'name': factory.make_name("name"),
            'partitions': [partition.id],
            }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of partition does not "
            "belonging to node.")
        self.assertEquals({
            'partitions': [
                "Select a valid choice. %s is not one of the available "
                "choices." % partition.id,
                ]}, form._errors)

    def test_creates_volume_group_with_name_and_uuid(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        name = factory.make_name("vg")
        vguuid = "%s" % uuid.uuid4()
        data = {
            'name': name,
            'uuid': vguuid,
            'block_devices': [block_device.id],
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        self.assertEquals(name, volume_group.name)
        self.assertEquals(vguuid, volume_group.uuid)

    def test_creates_volume_group_with_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        block_device_ids = [
            block_device.id
            for block_device in block_devices
        ]
        data = {
            'name': factory.make_name("vg"),
            'block_devices': block_device_ids,
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertItemsEqual(block_devices, block_devices_in_vg)

    def test_creates_volume_group_with_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=MIN_BLOCK_DEVICE_SIZE * 2)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        partition_ids = [
            partition.id
            for partition in partitions
        ]
        data = {
            'name': factory.make_name("vg"),
            'partitions': partition_ids,
        }
        form = CreateVolumeGroupForm(node, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        volume_group = form.save()
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertItemsEqual(partitions, partitions_in_vg)

    def test_creates_volume_group_with_block_devices_and_partitions(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        block_device_ids = [
            block_device.id
            for block_device in block_devices
        ]
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=MIN_BLOCK_DEVICE_SIZE * 2)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        partition_ids = [
            partition.id
            for partition in partitions
        ]
        data = {
            'name': factory.make_name("vg"),
            'block_devices': block_device_ids,
            'partitions': partition_ids,
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
        self.assertItemsEqual(block_devices, block_devices_in_vg)
        self.assertItemsEqual(partitions, partitions_in_vg)
