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
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block


class TestPartitionTable(MAASServerTestCase):
    """Tests for the `PartitionTable` model."""

    def test_get_node_returns_block_device_node(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.node, partition_table.get_node())

    def test_get_size_returns_block_device_size_minus_initial_offset(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.size - PARTITION_TABLE_EXTRA_SPACE,
            partition_table.get_size())

    def test_get_block_size_returns_block_device_block_size(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.block_size,
            partition_table.get_block_size())

    def test_add_misaligned_partition(self):
        """Tests whether a partition size are adjusted according to
        device block size."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition(
            size=MIN_BLOCK_DEVICE_SIZE + 54)
        self.assertEqual(
            round_size_to_nearest_block(
                MIN_BLOCK_DEVICE_SIZE + 54, block_size),
            partition.size)

    def test_add_partition_no_size(self):
        """Tests whether a partition with no specified size stretches to the
        end of the device"""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        self.assertEqual(
            partition.size, MIN_BLOCK_DEVICE_SIZE * 2)

    def test_add_second_partition_no_size(self):
        """Tests whether a second partition with no specified size starts from
        the end of the previous partition and stretches to the end of the
        device."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
        partition = partition_table.add_partition()
        self.assertEqual(MIN_BLOCK_DEVICE_SIZE * 2, partition.size)

    def test_add_partition_to_full_device(self):
        """Tests whether we fail to add a partition to an already full device.
        """
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition_table.add_partition()
        self.assertRaises(
            ValidationError, partition_table.add_partition)

    def test_get_available_size(self):
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
        self.assertEquals(
            MIN_BLOCK_DEVICE_SIZE * 2, partition_table.get_available_size())

    def test_get_available_size_skips_partitions(self):
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        ignore_partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
            ]
        partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
        self.assertEquals(
            MIN_BLOCK_DEVICE_SIZE * 2,
            partition_table.get_available_size(
                ignore_partitions=ignore_partitions))
