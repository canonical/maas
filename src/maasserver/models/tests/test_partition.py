# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from unittest.mock import sentinel
from uuid import uuid4

from django.core.exceptions import ValidationError

from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.models import partition as partition_module
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.filesystemgroup import VolumeGroup
from maasserver.models.partition import (
    MIN_PARTITION_SIZE,
    Partition,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.partitiontable import (
    BIOS_GRUB_PARTITION_SIZE,
    PARTITION_TABLE_EXTRA_SPACE,
    PREP_PARTITION_SIZE,
)
from maasserver.storage_layouts import VMFS6StorageLayout, VMFS7StorageLayout
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.test_storage_layouts import LARGE_BLOCK_DEVICE
from maasserver.utils.orm import reload_object


class TestPartitionManager(MAASServerTestCase):
    """Tests for the `PartitionManager`."""

    def test_get_free_partitions_for_node(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        free_partitions = [
            partition_table.add_partition(size=MIN_PARTITION_SIZE)
            for _ in range(2)
        ]
        # Make used partitions.
        for _ in range(2):
            factory.make_Filesystem(
                partition=partition_table.add_partition(
                    size=MIN_PARTITION_SIZE
                )
            )
        self.assertCountEqual(
            free_partitions,
            Partition.objects.get_free_partitions_for_node(node),
        )

    def test_get_partitions_in_filesystem_group(self):
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        block_device_with_partitions = factory.make_PhysicalBlockDevice(
            node=node
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device_with_partitions
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=partition,
            filesystem_group=filesystem_group,
        )
        partitions_in_filesystem_group = (
            Partition.objects.get_partitions_in_filesystem_group(
                filesystem_group
            )
        )
        self.assertCountEqual([partition], partitions_in_filesystem_group)

    def test_get_partition_by_id_or_name_returns_valid_with_id(self):
        node = factory.make_Node()
        disk = factory.make_BlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=disk)
        partition = partition_table.add_partition()
        self.assertEqual(
            partition,
            Partition.objects.get_partition_by_id_or_name(
                node.current_config, partition.id
            ),
        )

    def test_get_partition_by_id_or_name_returns_valid_with_name(self):
        node = factory.make_Node()
        disk = factory.make_BlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=disk)
        partition = partition_table.add_partition()
        self.assertEqual(
            partition,
            Partition.objects.get_partition_by_id_or_name(
                node.current_config, partition.name
            ),
        )

    def test_get_partition_by_name_on_right_disk(self):
        node = factory.make_Node()
        disk = factory.make_BlockDevice(node=node, name="sda")
        partition_table = factory.make_PartitionTable(block_device=disk)
        partition = partition_table.add_partition()

        # another node with a partition with same name as the first
        node2 = factory.make_Node()
        disk2 = factory.make_BlockDevice(node=node2, name="sda")
        partition_table2 = factory.make_PartitionTable(block_device=disk2)
        partition2 = partition_table2.add_partition()
        self.assertEqual(partition.get_name(), partition2.get_name())

        self.assertEqual(
            partition,
            Partition.objects.get_partition_by_id_or_name(
                node.current_config, partition.get_name()
            ),
        )

    def test_get_partition_by_name_not_found_other_disk(self):
        node = factory.make_Node()
        disk = factory.make_BlockDevice(node=node, name="sda")
        partition_table = factory.make_PartitionTable(block_device=disk)
        partition = partition_table.add_partition()
        node2 = factory.make_Node()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            node2.current_config,
            partition.get_name(),
        )

    def test_get_partition_by_id_or_name_invalid_id(self):
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            factory.make_NodeConfig(),
            random.randint(1000, 5000),
        )

    def test_get_partition_by_id_or_name_empty_string(self):
        factory.make_Partition()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            factory.make_NodeConfig(),
            "",
        )

    def test_get_partition_by_id_or_name_invalid_part_seperator(self):
        partition = factory.make_Partition()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            factory.make_NodeConfig(),
            f"{partition.partition_table.block_device.get_name()}part{partition.index}",
        )

    def test_get_partition_by_id_or_name_invalid_part_number(self):
        partition = factory.make_Partition()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            factory.make_NodeConfig(),
            f"{partition.partition_table.block_device.get_name()}partX",
        )

    def test_filter_by_tags_returns_partitions_with_one_tag(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        other_tags = [factory.make_name("tag") for _ in range(3)]
        partitions_with_tags = [
            factory.make_Partition(tags=tags) for _ in range(3)
        ]
        for _ in range(3):
            factory.make_Partition(tags=other_tags)
        self.assertCountEqual(
            partitions_with_tags, Partition.objects.filter_by_tags([tags[0]])
        )

    def test_filter_by_tags_returns_partitions_with_all_tags(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        other_tags = [factory.make_name("tag") for _ in range(3)]
        partitions_with_tags = [
            factory.make_Partition(tags=tags) for _ in range(3)
        ]
        for _ in range(3):
            factory.make_Partition(tags=other_tags)
        self.assertCountEqual(
            partitions_with_tags, Partition.objects.filter_by_tags(tags)
        )

    def test_filter_by_tags_returns_no_devices(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        for _ in range(3):
            factory.make_Partition(tags=tags)
        self.assertCountEqual(
            [], Partition.objects.filter_by_tags([factory.make_name("tag")])
        )

    def test_filter_by_tags_returns_devices_with_iterable(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        other_tags = [factory.make_name("tag") for _ in range(3)]
        devices_with_tags = [
            factory.make_Partition(tags=tags) for _ in range(3)
        ]
        for _ in range(3):
            factory.make_Partition(tags=other_tags)

        def tag_generator():
            yield from tags

        self.assertCountEqual(
            devices_with_tags,
            Partition.objects.filter_by_tags(tag_generator()),
        )

    def test_filter_by_tags_raise_TypeError_when_unicode(self):
        self.assertRaises(TypeError, Partition.objects.filter_by_tags, "test")

    def test_filter_by_tags_raise_TypeError_when_not_iterable(self):
        self.assertRaises(
            TypeError, Partition.objects.filter_by_tags, object()
        )


class TestPartition(MAASServerTestCase):
    """Tests for the `Partition` model."""

    def test_name(self):
        block_device_name = factory.make_name("bd")
        block_device = factory.make_PhysicalBlockDevice(name=block_device_name)
        table = factory.make_PartitionTable(block_device=block_device)
        partition = factory.make_Partition(partition_table=table)
        self.assertEqual("%s-part1" % block_device_name, partition.name)

    def test_path(self):
        block_device = factory.make_PhysicalBlockDevice()
        table = factory.make_PartitionTable(block_device=block_device)
        partition = factory.make_Partition(partition_table=table)
        self.assertEqual("%s-part1" % block_device.path, partition.path)

    def test_get_name(self):
        block_device_name = factory.make_name("bd")
        block_device = factory.make_PhysicalBlockDevice(name=block_device_name)
        table = factory.make_PartitionTable(block_device=block_device)
        partition = factory.make_Partition(partition_table=table)
        self.assertEqual("%s-part1" % block_device_name, partition.get_name())

    def test_get_node_returns_partition_table_node(self):
        partition = factory.make_Partition()
        self.assertEqual(
            partition.partition_table.get_node(), partition.get_node()
        )

    def test_get_used_size_returns_used_zero_when_no(self):
        partition = factory.make_Partition()
        self.assertEqual(partition.get_used_size(), 0)

    def test_get_used_size_returns_partition_size_when_filesystem(self):
        partition = factory.make_Partition()
        factory.make_Filesystem(partition=partition)
        self.assertEqual(partition.get_used_size(), partition.size)

    def test_get_available_size_returns_available_size(self):
        partition = factory.make_Partition()
        self.assertEqual(
            partition.get_available_size(),
            partition.size - partition.get_used_size(),
        )

    def test_get_block_size_returns_partition_table_block_size(self):
        partition = factory.make_Partition()
        self.assertEqual(
            partition.partition_table.get_block_size(),
            partition.get_block_size(),
        )

    def test_set_uuid_if_missing(self):
        table = factory.make_PartitionTable()
        partition = factory.make_Partition(partition_table=table)
        self.assertIsNotNone(partition.uuid)

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT
        )
        partition = factory.make_Partition(partition_table=table, uuid=uuid)
        partition.save()
        self.assertEqual("%s" % uuid, partition.uuid)

    def test_size_is_rounded_to_current_block(self):
        partition = factory.make_Partition()
        partition.size = PARTITION_ALIGNMENT_SIZE * 4
        partition.size += 1
        partition.save()
        self.assertEqual(PARTITION_ALIGNMENT_SIZE * 4, partition.size)

    def test_validate_enough_space_for_new_partition(self):
        partition_table = factory.make_PartitionTable()
        partition_table.add_partition()
        error = self.assertRaises(
            ValidationError,
            factory.make_Partition,
            partition_table=partition_table,
            size=MIN_PARTITION_SIZE,
        )
        self.assertEqual(
            {
                "size": [
                    "Partition cannot be saved; not enough free space "
                    "on the block device."
                ]
            },
            error.message_dict,
        )

    def test_validate_enough_space_for_resize_partition(self):
        partition_table = factory.make_PartitionTable()
        partition = partition_table.add_partition()
        partition.size += PARTITION_ALIGNMENT_SIZE * 2
        error = self.assertRaises(ValidationError, partition.save)
        self.assertEqual(
            {
                "size": [
                    "Partition %s cannot be resized to fit on the "
                    "block device; not enough free space." % partition.id
                ]
            },
            error.message_dict,
        )

    def test_test_cannot_create_mbr_partition_larger_than_2TiB(self):
        block_device = factory.make_BlockDevice(size=3 * (1024**4))  # 3TiB
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.MBR
        )
        error = self.assertRaises(
            ValidationError,
            factory.make_Partition,
            partition_table=partition_table,
            size=partition_table.get_available_size(),
        )
        self.assertEqual(
            {
                "size": [
                    "Partition cannot be saved; size is larger than "
                    "the MBR 2TiB maximum."
                ]
            },
            error.message_dict,
        )

    def test_test_cannot_resize_mbr_partition_to_more_than_2TiB(self):
        block_device = factory.make_BlockDevice(size=3 * (1024**4))  # 3TiB
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.MBR
        )
        partition = partition_table.add_partition(size=1 * (1024**4))
        partition.size = 2.5 * (1024**4)
        error = self.assertRaises(ValidationError, partition.save)
        self.assertEqual(
            {
                "size": [
                    "Partition %s cannot be resized to fit on the "
                    "block device; size is larger than the MBR "
                    "2TiB maximum." % partition.id
                ]
            },
            error.message_dict,
        )

    def test_validate_can_save_gpt_larger_than_2TiB(self):
        block_device = factory.make_BlockDevice(size=3 * (1024**4))  # 3TiB
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.GPT
        )
        # Test is that an error is not raised.
        partition_table.add_partition()

    def test_validate_enough_space_will_round_down_a_block(self):
        partition_table = factory.make_PartitionTable()
        partition = partition_table.add_partition()
        prev_size = partition.size
        partition.size += partition_table.get_block_size()
        partition.save()
        self.assertEqual(prev_size, partition.size)

    def test_get_effective_filesystem(self):
        mock_get_effective_filesystem = self.patch_autospec(
            partition_module, "get_effective_filesystem"
        )
        mock_get_effective_filesystem.return_value = sentinel.filesystem
        partition = factory.make_Partition()
        self.assertEqual(
            sentinel.filesystem, partition.get_effective_filesystem()
        )

    def test_partition_index_start_at_1_for_gpt(self):
        node = factory.make_Node(bios_boot_method="uefi")
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.GPT
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(4)
        ]
        for index, partition in enumerate(partitions, 1):
            self.assertEqual(partition.index, index)

    def test_partition_index_start_at_2_for_amd64_not_uefi(self):
        node = factory.make_Node(
            bios_boot_method="pxe", architecture="amd64/generic"
        )
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4)
            + PARTITION_TABLE_EXTRA_SPACE
            + BIOS_GRUB_PARTITION_SIZE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.GPT
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(4)
        ]
        for index, partition in enumerate(partitions, 2):
            self.assertEqual(partition.index, index)

    def test_partition_index_start_at_2_for_ppc64el(self):
        node = factory.make_Node(
            architecture="ppc64el/generic",
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(
                (MIN_PARTITION_SIZE * 4)
                + PARTITION_TABLE_EXTRA_SPACE
                + PREP_PARTITION_SIZE
            ),
        )
        node.boot_disk = block_device
        node.save()
        # replace the cached object since the node is updated earlier
        node.current_config.node = node

        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.GPT
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(4)
        ]
        for index, partition in enumerate(partitions, 2):
            self.assertEqual(partition.index, index)

    def test_partition_index_vmfs6(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        pt = bd.get_partitiontable()
        self.assertEqual(
            [1, 2, 3, 5, 6, 7, 8, 9],
            list(
                pt.partitions.order_by("index").values_list("index", flat=True)
            ),
        )

    def test_partition_index_vmfs7(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout.configure()
        pt = bd.get_partitiontable()
        self.assertEqual(
            [1, 5, 6, 7, 8],
            list(
                pt.partitions.order_by("index").values_list("index", flat=True)
            ),
        )

    def test_partition_index_start_at_2_for_amd64_gpt(self):
        node = factory.make_Node(
            architecture="amd64/generic",
            bios_boot_method="pxe",
            with_boot_disk=False,
        )
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(
                (2 * (1024**4))
                + PARTITION_TABLE_EXTRA_SPACE
                + BIOS_GRUB_PARTITION_SIZE
            ),
        )
        node.boot_disk = block_device
        node.save()
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.GPT
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(4)
        ]
        for index, partition in enumerate(partitions, 2):
            self.assertEqual(index, partition.index)

    def test_partition_index_for_mbr_extended(self):
        block_device = factory.make_PhysicalBlockDevice(
            size=(MIN_BLOCK_DEVICE_SIZE * 6) + PARTITION_TABLE_EXTRA_SPACE
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.MBR
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(6)
        ]
        self.assertEqual(
            [1, 2, 3, 5, 6, 7],  # partition 4 is used for extended
            [partition.index for partition in partitions],
        )

    def test_is_vmfs_partition_layout6(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout_name = layout.configure()
        pt = bd.get_partitiontable()
        for partition in pt.partitions.all():
            self.assertTrue(
                partition.is_vmfs_partition(),
                f"{layout_name} index {partition.index} is VMFS",
            )

    def test_is_vmfs_partition_layout7p(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout_name = layout.configure()
        pt = bd.get_partitiontable()
        for partition in pt.partitions.all():
            if partition.index >= 8:
                self.assertFalse(
                    partition.is_vmfs_partition(),
                    f"{layout_name} index {partition.index} is VMFS",
                )
            else:
                self.assertTrue(
                    partition.is_vmfs_partition(),
                    f"{layout_name} index {partition.index} is VMFS",
                )

    def test_is_vmfs_partition_false_no_vmfs(self):
        partition = factory.make_Partition()
        self.assertFalse(partition.is_vmfs_partition())

    def test_is_vmfs6_partition_false_different_block_device(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = VMFS6StorageLayout(node)
        layout.configure()
        other_bd_part = factory.make_Partition(node=node)
        self.assertFalse(other_bd_part.is_vmfs_partition())

    def test_is_vmfs7_partition_false_different_block_device(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = VMFS7StorageLayout(node)
        layout.configure()
        other_bd_part = factory.make_Partition(node=node)
        self.assertFalse(other_bd_part.is_vmfs_partition())

    def test_is_vmfs6_partition_false_extra_partition(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node, {"root_size": 10 * 1024**3})
        layout.configure()
        pt = bd.get_partitiontable()
        extra_partition = pt.add_partition()
        self.assertFalse(extra_partition.is_vmfs_partition())

    def test_is_vmfs7_partition_false_extra_partition(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node, {"root_size": 10 * 1024**3})
        layout.configure()
        pt = bd.get_partitiontable()
        extra_partition = pt.add_partition()
        self.assertFalse(extra_partition.is_vmfs_partition())

    def test_delete_not_allowed_if_part_of_filesystem_group(self):
        partition = factory.make_Partition(
            size=1024**3, block_device_size=2 * 1024**3
        )
        VolumeGroup.objects.create_volume_group(
            factory.make_name("vg"), [], [partition]
        )
        error = self.assertRaises(ValidationError, partition.delete)
        self.assertEqual(
            "Cannot delete partition because its part of a volume group.",
            error.message,
        )

    def test_delete_not_allowed_if_part_of_vmfs6_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        pt = bd.get_partitiontable()
        partition = random.choice(list(pt.partitions.all()))
        self.assertRaises(ValidationError, partition.delete)

    def test_delete_not_allowed_if_part_of_vmfs7_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout.configure()
        pt = bd.get_partitiontable()
        partition = random.choice(list(pt.partitions.all()))
        self.assertRaises(ValidationError, partition.delete)

    def test_delete(self):
        partition = factory.make_Partition()
        partition.delete()
        self.assertIsNone(reload_object(partition))

    def test_delete_removes_partition_table_if_last_partition(self):
        partition_table = factory.make_PartitionTable()
        partition = factory.make_Partition(partition_table=partition_table)
        partition.delete()
        self.assertIsNone(reload_object(partition))
        self.assertIsNone(reload_object(partition_table))

    def test_delete_doesnt_remove_partition_table_if_not_last_partition(self):
        partition_table = factory.make_PartitionTable()
        partition1 = factory.make_Partition(partition_table=partition_table)
        partition2 = factory.make_Partition(partition_table=partition_table)
        partition2.delete()
        self.assertIsNotNone(reload_object(partition1))
        self.assertIsNotNone(reload_object(partition_table))
        self.assertIsNone(reload_object(partition2))

    def test_delete_partitiontable_before_partition_doesnt_raise_error(self):
        partition_table = factory.make_PartitionTable()
        factory.make_Partition(partition_table=partition_table)
        # Test is that no error is raised.
        partition_table.delete()

    def test_add_tag_adds_new_tag(self):
        partition = Partition()
        tag = factory.make_name("tag")
        partition.add_tag(tag)
        self.assertEqual([tag], partition.tags)

    def test_add_tag_doesnt_duplicate(self):
        partition = Partition()
        tag = factory.make_name("tag")
        partition.add_tag(tag)
        partition.add_tag(tag)
        self.assertEqual([tag], partition.tags)

    def test_remove_tag_deletes_tag(self):
        partition = Partition()
        tag = factory.make_name("tag")
        partition.add_tag(tag)
        partition.remove_tag(tag)
        self.assertEqual([], partition.tags)
