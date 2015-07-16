# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Partition`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from uuid import uuid4

from django.core.exceptions import ValidationError
from maasserver.enum import (
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import Partition
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPartitionManager(MAASServerTestCase):
    """Tests for the `PartitionManager`."""

    def test_get_free_partitions_for_node(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=MIN_BLOCK_DEVICE_SIZE * 4)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        free_partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        # Make used partitions.
        for _ in range(2):
            factory.make_Filesystem(
                partition=partition_table.add_partition(
                    size=MIN_BLOCK_DEVICE_SIZE))
        self.assertItemsEqual(
            free_partitions,
            Partition.objects.get_free_partitions_for_node(node))


class TestPartition(MAASServerTestCase):
    """Tests for the `Partition` model."""

    def test_get_node_returns_partition_table_node(self):
        partition = factory.make_Partition()
        self.assertEquals(
            partition.partition_table.get_node(), partition.get_node())

    def test_get_block_size_returns_partition_table_block_size(self):
        partition = factory.make_Partition()
        self.assertEquals(
            partition.partition_table.get_block_size(),
            partition.get_block_size())

    def test_set_uuid_if_missing(self):
        table = factory.make_PartitionTable()
        partition = factory.make_Partition(partition_table=table)
        self.assertIsNotNone(partition.uuid)

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT)
        partition = factory.make_Partition(partition_table=table, uuid=uuid)
        partition.save()
        self.assertEquals('%s' % uuid, partition.uuid)

    def test_start_end_block(self):
        """Tests the start_block, size_blocks and end_block helpers."""
        device = factory.make_BlockDevice(size=10 * 1000 ** 3, block_size=4096)
        partition_table = factory.make_PartitionTable(block_device=device)
        # A partition that takes up blocks 0, 1 and 2.
        partition = factory.make_Partition(partition_table=partition_table,
                                           start_offset=0,
                                           size=4096 * 3)

        self.assertEqual(partition.start_block, 0)
        self.assertEqual(partition.size_blocks, 3)
        self.assertEqual(partition.end_block, 2)

    def test_block_sizing(self):
        """Ensure start_block and  and size are rounded to block boundaries."""
        device = factory.make_BlockDevice(size=10 * 1000 ** 3, block_size=4096)
        # A billion bytes slightly misaligned.
        partition_size = 1 * 1000 ** 3
        partition_offset = device.block_size * 3 + 50
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(partition_table=partition_table,
                                           start_offset=partition_offset,
                                           size=partition_size)

        # Size should be larger than the desired.
        self.assertGreaterEqual(partition.size_blocks * device.block_size,
                                partition_size)
        # But not more than one block larger.
        self.assertLessEqual((partition.size_blocks - 1) * device.block_size,
                             partition_size)
        # Partition should start on the 4th block (we count from zero).
        self.assertEqual(partition.start_block, 3)

    def test_clean(self):
        """Ensure size and offset are rounded on save."""
        device = factory.make_BlockDevice(size=10 * 1000 ** 3, block_size=4096)
        # A billion bytes slightly misaligned.
        partition_size = 1 * 1000 ** 3
        partition_offset = device.block_size * 3 + 50
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(partition_table=partition_table,
                                           start_offset=partition_offset,
                                           size=partition_size)

        # Start should be slightly less than desired start.
        self.assertLessEqual(partition.start_offset, partition_offset)
        self.assertLess(partition_offset - partition.start_offset,
                        device.block_size)
        # Size should be no more than one block larger.
        self.assertLess(partition.size - partition_size, device.block_size)

    def test_size_validator(self):
        """Checks impossible values for size and offset"""
        device = factory.make_BlockDevice(size=10 * 1000 ** 3, block_size=4096)
        partition_table = factory.make_PartitionTable(block_device=device)

        # Should not be able to make a partition with zero blocks.
        self.assertRaises(ValidationError, factory.make_Partition,
                          **{'partition_table': partition_table,
                             'start_offset': 0,
                             'size': 0})
        # Should not be able to make a partition starting on block -1
        self.assertRaises(ValidationError, factory.make_Partition,
                          **{'partition_table': partition_table,
                             'start_offset': -1,
                             'size': 10})

    def test_overlap_prevention(self):
        """Checks whether overlap prevention works."""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # Create a partition occupying blocks 5, 6, 7, 8 and 9.
        factory.make_Partition(partition_table=partition_table,
                               start_offset=5 * block_size,
                               size=5 * block_size)
        # Uses blocks 3, 4, 5 and 6.
        self.assertRaises(ValidationError, factory.make_Partition,
                          **{'partition_table': partition_table,
                             'start_offset': 3 * block_size,
                             'size': 4 * block_size})
        # Uses blocks 8, 9, 10.
        self.assertRaises(ValidationError, factory.make_Partition,
                          **{'partition_table': partition_table,
                             'start_offset': 8 * block_size,
                             'size': 3 * block_size})
        # Uses blocks 6, 7, 8.
        self.assertRaises(ValidationError, factory.make_Partition,
                          **{'partition_table': partition_table,
                             'start_offset': 6 * block_size,
                             'size': 3 * block_size})
        # Should succeed - uses blocks 0, 1, 2.
        factory.make_Partition(partition_table=partition_table,
                               start_offset=0,
                               size=3 * block_size)

    def test_partition_past_end_of_device(self):
        """Attempt to allocate a partition past the end of the device."""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # Should not make a partition larger than the device
        self.assertRaises(ValidationError, factory.make_Partition,
                          **{'partition_table': partition_table,
                             'start_offset': 0,
                             'size': device.size + device.block_size})
        # Create a partition the size of the device
        partition = factory.make_Partition(partition_table=partition_table,
                                           start_offset=0,
                                           size=device.size)
        self.assertEqual(partition.size, device.size)

    def test_partition_add_filesystem(self):
        """Add a file system to a partition"""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        filesystem = partition.add_filesystem(fstype=FILESYSTEM_TYPE.EXT4)
        self.assertEquals(filesystem.partition_id, partition.id)
        self.assertEquals(filesystem.fstype, FILESYSTEM_TYPE.EXT4)

    def test_partition_add_second_filesystem(self):
        """Adding a second file system to a partition should fail"""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        partition.add_filesystem(fstype=FILESYSTEM_TYPE.EXT4)

        # Adding a second one should fail
        self.assertRaises(ValidationError, partition.add_filesystem,
                          **{'fstype': FILESYSTEM_TYPE.EXT4})

    def test_partition_remove_filesystem(self):
        """Tests filesystem removal from a partition"""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        partition.add_filesystem(fstype=FILESYSTEM_TYPE.EXT4)
        # After removal, partition.filesystem should be None
        partition.remove_filesystem()
        self.assertIsNone(partition.filesystem)

    def test_partition_remove_absent_filesystem(self):
        """Tests whether attempting to remove a non-existent FS fails"""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        # Removal should do nothing
        self.assertIsNone(partition.remove_filesystem())

    def test_get_filesystem_returns_filesystem(self):
        """Checks that the get_filesystem method returns the filesystem that's
        on the partition"""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        fs = factory.make_Filesystem(partition=partition)

        self.assertEqual(partition.filesystem.id, fs.id)

    def test_get_filesystem_returns_none(self):
        """Checks that the get_filesystem method returns none when there is no
        filesystem on the partition"""
        block_size = 1024
        device = factory.make_BlockDevice(size=10000 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()

        self.assertIsNone(partition.filesystem)
