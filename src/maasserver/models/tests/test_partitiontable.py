# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `PartitionTable`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []
from django.core.exceptions import ValidationError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPartitionTable(MAASServerTestCase):
    """Tests for the `PartitionTable` model."""

    def test_get_node_returns_block_device_node(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.node, partition_table.get_node())

    def test_get_size_returns_block_device_size(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.size, partition_table.get_size())

    def test_get_block_size_returns_block_device_block_size(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.block_size,
            partition_table.get_block_size())

    def test_add_aligned_partition(self):
        """Tests adding an aligned partition to an empty partition table"""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        block_size = partition_table.get_block_size()
        # A partition that spans blocks 10, 11, 12, 13, 14 and 15.
        partition = partition_table.add_partition(start_offset=10 * block_size,
                                                  size=6 * block_size)
        # Ensure the partition was created where we expected it.
        self.assertEqual(partition.start_block, 10)
        self.assertEqual(partition.size_blocks, 6)

    def test_is_free(self):
        """Test the is_region_free helper method"""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        # A partition that spans blocks 10, 11, 12, 13, 14, and 15.
        partition = partition_table.add_partition(
            start_offset=10 * block_size,
            size=6 * block_size)

        self.assertFalse(partition_table.is_region_free(partition.start_offset,
                                                        partition.size))
        # Region 0-9 should be free (10 blocks starting from block 0).
        self.assertTrue(partition_table.is_region_free(0, 10 * block_size))
        # Region 0-10 should not be free.
        self.assertFalse(partition_table.is_region_free(0, 11 * block_size))
        # Region 15-n should not be free.
        self.assertFalse(partition_table.is_region_free(15 * block_size,
                                                        11 * block_size))
        # Region 16-n should be free.
        self.assertTrue(partition_table.is_region_free(16 * block_size,
                                                       11 * block_size))

    def test_add_misaligned_partition(self):
        """Tests whether a partition offset and size are adjusted according to
        device block size"""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans blocks 10, 11, 12, 13, 14, 15 and 16.
        partition = partition_table.add_partition(
            start_offset=10 * block_size + 42,  # Misalign by 42 bytes.
            size=6 * block_size + 54)           # Six times nine.

        # Check the offset and size are round
        self.assertEqual(partition.start_offset % block_size, 0)
        self.assertEqual(partition.size % block_size, 0)
        self.assertEqual(partition.start_block, 10)  # Still block 10.
        self.assertEqual(partition.size_blocks, 7)   # Spans 7 blocks now.

    def test_add_partition_no_offset_empty(self):
        """Tests whether not giving a partition offset will place it block 0 of
        an empty drive."""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans blocks 0, 1, 2, 3, 4 and 5.
        partition = partition_table.add_partition(size=6 * block_size)
        self.assertEqual(partition.start_block, 0)
        self.assertEqual(partition.size_blocks, 6)

    def test_add_partition_movable_offset(self):
        """Tests whether a new partition added without specifying start is
        fitted in the lowest available space"""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        # A partition that spans blocks 10, 11, 12, 13, 14 and 15 leaving 0-9
        # and 16-end unallocated.
        partition0 = partition_table.add_partition(
            start_offset=10 * block_size,
            size=6 * block_size)

        # A partition of 10 blocks should be placed at block 0
        partition1 = partition_table.add_partition(
            size=10 * block_size)
        self.assertEqual(partition1.start_block, 0)
        self.assertEqual(partition1.size_blocks, partition0.start_block)

    def test_add_partition_no_offset(self):
        """Tests whether a new partition added without specifying start is
        fitted in the lowest available space"""
        block_size = 4096
        device = factory.make_BlockDevice(size=10 * 1000 ** 3,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        # A partition that spans blocks 10, 11, 12, 13, 14 and 15 leaving 0-9
        # and 16-end unallocated.
        partition0 = partition_table.add_partition(
            start_offset=10 * block_size,
            size=6 * block_size)
        # A partition of 15 blocks should fail to be allocated.
        self.assertRaises(ValidationError, partition_table.add_partition,
                          **{'size': 15 * block_size})
        # A partition of 10 blocks should be placed at block 0.
        partition1 = partition_table.add_partition(
            size=10 * block_size)
        self.assertEqual(partition1.start_block, 0)
        self.assertEqual(partition1.size_blocks, partition0.start_block)

    def test_add_partition_no_size(self):
        """Tests whether a partition with no speciefied size stretches to the
        end of the device"""
        block_size = 4096
        device = factory.make_BlockDevice(size=10000 * block_size,
                                          block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans from block 10 until the end of the device.
        partition = partition_table.add_partition(start_offset=10 * block_size)
        # It should start at block 10 and have 9990 blocks.
        self.assertEqual(partition.start_block, 10)
        self.assertEqual(partition.size_blocks,
                         device.size / block_size - partition.start_block)
