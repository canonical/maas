# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Filesystem`."""

__all__ = []

import re
from uuid import uuid4

from django.core.exceptions import ValidationError
from maasserver.models.filesystem import Filesystem
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException


class TestFilesystemManager(MAASServerTestCase):
    """Tests for the `FilesystemManager`."""

    def test_filter_by_node(self):
        node = factory.make_Node()
        boot_bd = node.blockdevice_set.first()
        root_partition = boot_bd.partitiontable_set.first().partitions.first()
        root_fs = root_partition.filesystem_set.first()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        bd_for_partitions = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=bd_for_partitions)
        partition = factory.make_Partition(partition_table=partition_table)
        filesystem_on_bd = factory.make_Filesystem(block_device=block_device)
        filesystem_on_partition = factory.make_Filesystem(partition=partition)
        self.assertItemsEqual(
            [root_fs, filesystem_on_bd, filesystem_on_partition],
            Filesystem.objects.filter_by_node(node))


class TestFilesystem(MAASServerTestCase):
    """Tests for the `Filesystem` model."""

    def test_get_node_returns_partition_node(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEqual(
            fs.partition.get_node(), fs.get_node())

    def test_get_node_returns_block_device_node(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(
            fs.block_device.node, fs.get_node())

    def test_get_node_returns_None_when_partition_and_block_device_None(self):
        fs = Filesystem()
        self.assertIsNone(fs.get_node())

    def test_get_size_returns_partition_size(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEqual(
            fs.partition.size, fs.get_size())

    def test_get_size_returns_block_device_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(
            fs.block_device.size, fs.get_size())

    def test_get_size_returns_0_when_partition_and_block_device_None(self):
        fs = Filesystem()
        self.assertEqual(0, fs.get_size())

    def test_get_block_size_returns_partition_block_size(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEqual(
            fs.partition.get_block_size(), fs.get_block_size())

    def test_get_block_size_returns_block_device_block_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(
            fs.block_device.block_size, fs.get_block_size())

    def test_get_block_size_returns_0_when_partition_and_device_None(self):
        fs = Filesystem()
        self.assertEqual(0, fs.get_block_size())

    def test_cannot_save_if_boot_partition_and_block_device_missing(self):
        fs = Filesystem()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': ['One of partition or block_device "
                    "must be specified.']}")):
            fs.save()

    def test_cannot_save_if_both_boot_partition_and_block_device_exists(self):
        fs = Filesystem()
        fs.block_device = factory.make_PhysicalBlockDevice()
        fs.partition = factory.make_Partition()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': ['Only one of partition or block_device "
                    "can be specified.']}")):
            fs.save()

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        fs = factory.make_Filesystem(uuid=uuid)
        self.assertEqual('%s' % uuid, fs.uuid)

    def test_get_parent_returns_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(block_device, filesystem.get_parent())

    def test_get_parent_returns_partition(self):
        partition = factory.make_Partition()
        filesystem = factory.make_Filesystem(partition=partition)
        self.assertEqual(partition, filesystem.get_parent())

    def test_cannot_create_filesystem_directly_on_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': ['Cannot place filesystem directly on the "
                    "boot disk. Create a partition on the boot disk first "
                    "and then format the partition.']}")):
            factory.make_Filesystem(block_device=boot_disk)

    def test_can_create_filesystem_on_partition_on_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=boot_disk)
        partition = factory.make_Partition(partition_table=partition_table)
        # Test is that an error is not raised.
        factory.make_Filesystem(partition=partition)
