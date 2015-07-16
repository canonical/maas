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
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import Partition
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
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        # A partition that spans blocks 10-45.
        partition = partition_table.add_partition(
            start_offset=10 * block_size, size=35 * block_size)
        # Ensure the partition was created where we expected it.
        self.assertEqual(10, partition.start_block)
        self.assertEqual(35, partition.size_blocks)

    def test_is_free(self):
        """Test the is_region_free helper method"""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        # A partition that spans blocks 10-45.
        partition = partition_table.add_partition(
            start_offset=10 * block_size, size=35 * block_size)

        self.assertFalse(
            partition_table.is_region_free(
                partition.start_offset, partition.size))
        # Region 0-9 should be free (10 blocks starting from block 0).
        self.assertTrue(partition_table.is_region_free(0, 10 * block_size))
        # Region 0-10 should not be free.
        self.assertFalse(partition_table.is_region_free(0, 11 * block_size))
        # Region 15-26 should not be free.
        self.assertFalse(
            partition_table.is_region_free(
                15 * block_size, 11 * block_size))
        # Region 45-56 should be free.
        self.assertTrue(
            partition_table.is_region_free(
                45 * block_size, 11 * block_size))

    def test_add_misaligned_partition(self):
        """Tests whether a partition offset and size are adjusted according to
        device block size"""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans blocks 10-35.
        partition = partition_table.add_partition(
            start_offset=10 * block_size + 42,  # Misalign by 42 bytes.
            size=35 * block_size + 54)          # Six times nine.

        # Check the offset and size are round
        self.assertEqual(0, partition.start_offset % block_size)
        self.assertEqual(0, partition.size % block_size)
        self.assertEqual(
            10, partition.start_block, "Should start on block 10.")
        self.assertEqual(
            36, partition.size_blocks, "Should span 36 blocks.")

    def test_add_partition_no_offset_empty(self):
        """Tests whether not giving a partition offset will place it block 0 of
        an empty drive."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans blocks 0-35.
        partition = partition_table.add_partition(size=35 * block_size)
        self.assertEqual(0, partition.start_block)
        self.assertEqual(35, partition.size_blocks)

    def test_add_partition_no_offset(self):
        """Tests whether a new partition added without specifying start is
        placed either at block 0 if the drive has no partitions, or at the
        first free block after the last partition."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition of 35 blocks spanning blocks 0 to 35.
        partition0 = partition_table.add_partition(size=35 * block_size)
        self.assertEqual(0, partition0.start_block)
        self.assertEqual(34, partition0.end_block)
        self.assertEqual(35, partition0.size_blocks)

        # A partition of 35 blocks should start on block 35
        partition1 = partition_table.add_partition(size=35 * block_size)
        self.assertEqual(35, partition1.start_block)
        self.assertEqual(35, partition1.size_blocks)

    def test_add_partition_no_size(self):
        """Tests whether a partition with no specified size stretches to the
        end of the device"""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=10000 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans from block 10 until the end of the device.
        partition = partition_table.add_partition(start_offset=10 * block_size)
        # It should start at block 10 and have 9990 blocks.
        self.assertEqual(10, partition.start_block)
        self.assertEqual(
            partition.size_blocks,
            device.size / block_size - partition.start_block)

    def test_add_first_partition_no_size(self):
        """Tests whether a partition with no specified offset or size starts
        from block 0 of an empty drive and fills the device."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=10000 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans the whole device.
        partition = partition_table.add_partition()
        self.assertEqual(0, partition.start_block, 0)
        self.assertEqual(device.size / block_size, partition.size_blocks)

    def test_add_second_partition_no_size(self):
        """Tests whether a second partition with no specified size starts from
        the end of the previous partition and stretches to the end of the
        device."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans from block 0-35.
        partition = partition_table.add_partition(size=35 * block_size)

        # A partition that spans from block 35 until the end of the device.
        partition = partition_table.add_partition()
        self.assertEqual(35, partition.start_block)
        self.assertEqual(
            device.size / block_size - partition.start_block,
            partition.size_blocks)

    def test_add_partition_to_full_device(self):
        """Tests whether we fail to add a partition to an already full device.
        """
        block_size = 4096
        device = factory.make_BlockDevice(
            size=10000 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)

        # A partition that spans the whole device.
        partition = partition_table.add_partition()
        self.assertIsInstance(partition, Partition)
        self.assertRaises(
            ValidationError, partition_table.add_partition, **{
                'start_offset': 6 * block_size,
                'size': 3 * block_size})
