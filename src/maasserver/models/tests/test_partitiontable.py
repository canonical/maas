# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `PartitionTable`."""


from django.core.exceptions import ValidationError

from maasserver.enum import FILESYSTEM_GROUP_TYPE, PARTITION_TABLE_TYPE
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import (
    MAX_PARTITION_SIZE_FOR_MBR,
    MIN_PARTITION_SIZE,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.partitiontable import (
    BIOS_GRUB_PARTITION_SIZE,
    PARTITION_TABLE_EXTRA_SPACE,
    PREP_PARTITION_SIZE,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block


class TestPartitionTable(MAASServerTestCase):
    """Tests for the `PartitionTable` model."""

    def test_get_node_returns_block_device_node(self):
        partition_table = factory.make_PartitionTable()
        self.assertEqual(
            partition_table.block_device.node, partition_table.get_node()
        )

    def test_get_size_returns_block_device_size_minus_initial_offset(self):
        partition_table = factory.make_PartitionTable()
        self.assertEqual(
            round_size_to_nearest_block(
                partition_table.block_device.size
                - PARTITION_TABLE_EXTRA_SPACE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            partition_table.get_size(),
        )

    def test_get_size_returns_block_device_size_minus_ppc64el(self):
        node = factory.make_Node(architecture="ppc64el/generic")
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        self.assertEqual(
            round_size_to_nearest_block(
                partition_table.block_device.size
                - PARTITION_TABLE_EXTRA_SPACE
                - PREP_PARTITION_SIZE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            partition_table.get_size(),
        )

    def test_get_size_returns_block_device_size_minus_amd64_gpt(self):
        node = factory.make_Node(architecture="amd64/generic")
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=2 * (1024 ** 4)
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        self.assertEqual(
            round_size_to_nearest_block(
                partition_table.block_device.size
                - PARTITION_TABLE_EXTRA_SPACE
                - BIOS_GRUB_PARTITION_SIZE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            partition_table.get_size(),
        )

    def test_get_block_size_returns_block_device_block_size(self):
        partition_table = factory.make_PartitionTable()
        self.assertEqual(
            partition_table.block_device.block_size,
            partition_table.get_block_size(),
        )

    def test_add_misaligned_partition(self):
        """Tests whether a partition size are adjusted according to
        partition alignment size (4MiB)."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_PARTITION_SIZE * 2 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition(size=MIN_PARTITION_SIZE + 54)
        self.assertEqual(
            round_size_to_nearest_block(
                MIN_PARTITION_SIZE + 54, PARTITION_ALIGNMENT_SIZE, False
            ),
            partition.size,
        )

    def test_add_partition_no_size(self):
        """Tests whether a partition with no specified size stretches to the
        end of the device"""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 2 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = partition_table.add_partition()
        self.assertEqual(partition.size, MIN_BLOCK_DEVICE_SIZE * 2)

    def test_add_partition_no_size_sets_mbr_max(self):
        block_size = 4096
        device = factory.make_BlockDevice(
            size=3 * (1024 ** 4), block_size=block_size
        )
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=device
        )
        partition = partition_table.add_partition()
        self.assertEqual(
            round_size_to_nearest_block(
                MAX_PARTITION_SIZE_FOR_MBR, PARTITION_ALIGNMENT_SIZE, False
            ),
            partition.size,
        )

    def test_add_second_partition_no_size(self):
        """Tests whether a second partition with no specified size starts from
        the end of the previous partition and stretches to the end of the
        device."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_PARTITION_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition_table.add_partition(size=MIN_PARTITION_SIZE)
        partition = partition_table.add_partition()
        self.assertEqual(MIN_PARTITION_SIZE * 2, partition.size)

    def test_add_partition_to_full_device(self):
        """Tests whether we fail to add a partition to an already full device."""
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition_table.add_partition()
        self.assertRaises(ValidationError, partition_table.add_partition)

    def test_get_overhead_size(self):
        node = factory.make_Node(bios_boot_method="pxe")
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        self.assertEquals(
            PARTITION_TABLE_EXTRA_SPACE, partition_table.get_overhead_size()
        )

    def test_get_overhead_size_for_ppc64el(self):
        node = factory.make_Node(architecture="ppc64el/generic")
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        self.assertEquals(
            PARTITION_TABLE_EXTRA_SPACE + PREP_PARTITION_SIZE,
            partition_table.get_overhead_size(),
        )

    def test_get_overhead_size_for_amd64_gpt(self):
        node = factory.make_Node(architecture="amd64/generic")
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=2 * (1024 ** 4)
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        self.assertEquals(
            PARTITION_TABLE_EXTRA_SPACE + BIOS_GRUB_PARTITION_SIZE,
            partition_table.get_overhead_size(),
        )

    def test_get_available_size(self):
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_PARTITION_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition_table.add_partition(size=MIN_PARTITION_SIZE)
        self.assertEqual(
            MIN_PARTITION_SIZE * 2, partition_table.get_available_size()
        )

    def test_get_available_size_skips_partitions(self):
        block_size = 4096
        device = factory.make_BlockDevice(
            size=MIN_PARTITION_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        ignore_partitions = [
            partition_table.add_partition(size=MIN_PARTITION_SIZE)
            for _ in range(2)
        ]
        partition_table.add_partition(size=MIN_PARTITION_SIZE)
        self.assertEqual(
            MIN_PARTITION_SIZE * 2,
            partition_table.get_available_size(
                ignore_partitions=ignore_partitions
            ),
        )

    def test_save_sets_table_type_to_MBR_for_arm64(self):
        node = factory.make_Node(
            architecture="arm64/generic", with_boot_disk=False
        )
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=boot_disk)
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

    def test_clean_no_partition_table_on_logical_volume(self):
        node = factory.make_Node()
        virtual_device = factory.make_VirtualBlockDevice(node=node)
        error = self.assertRaises(
            ValidationError,
            factory.make_PartitionTable,
            block_device=virtual_device,
        )
        self.assertEqual(
            {
                "block_device": [
                    "Cannot create a partition table on a logical volume."
                ]
            },
            error.message_dict,
        )

    def test_clean_no_partition_table_on_bcache(self):
        node = factory.make_Node()
        bcache_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE, node=node
        )
        bcache_device = bcache_group.virtual_device
        error = self.assertRaises(
            ValidationError,
            factory.make_PartitionTable,
            block_device=bcache_device,
        )
        self.assertEqual(
            {
                "block_device": [
                    "Cannot create a partition table on a Bcache volume."
                ]
            },
            error.message_dict,
        )
