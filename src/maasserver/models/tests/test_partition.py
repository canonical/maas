# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Partition`."""


import random
from unittest.mock import sentinel
from uuid import uuid4

from django.core.exceptions import ValidationError
from testtools.matchers import Equals

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
from maasserver.storage_layouts import VMFS6StorageLayout
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
        self.assertItemsEqual(
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
        self.assertItemsEqual([partition], partitions_in_filesystem_group)

    def test_get_partition_by_id_or_name_returns_valid_with_id(self):
        partition = factory.make_Partition()
        self.assertEqual(
            partition,
            Partition.objects.get_partition_by_id_or_name(partition.id),
        )

    def test_get_partition_by_id_or_name_returns_valid_with_name(self):
        partition = factory.make_Partition()
        self.assertEqual(
            partition,
            Partition.objects.get_partition_by_id_or_name(partition.name),
        )

    def test_get_partition_by_id_or_name_invalid_id(self):
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            random.randint(1000, 5000),
        )

    def test_get_partition_by_id_or_name_empty_string(self):
        factory.make_Partition()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            "",
        )

    def test_get_partition_by_id_or_name_invalid_part_seperator(self):
        partition = factory.make_Partition()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            "%spart%s"
            % (
                partition.partition_table.block_device.get_name(),
                partition.get_partition_number(),
            ),
        )

    def test_get_partition_by_id_or_name_invalid_part_number(self):
        partition = factory.make_Partition()
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            "%spartX" % (partition.partition_table.block_device.get_name()),
        )

    def test_get_partition_by_id_or_name_by_id_invalid_table(self):
        partition_table = factory.make_PartitionTable()
        other_table = factory.make_PartitionTable()
        partition = factory.make_Partition(partition_table=partition_table)
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            partition.id,
            other_table,
        )

    def test_get_partition_by_id_or_name_by_name_invalid_table(self):
        partition_table = factory.make_PartitionTable()
        other_table = factory.make_PartitionTable()
        partition = factory.make_Partition(partition_table=partition_table)
        self.assertRaises(
            Partition.DoesNotExist,
            Partition.objects.get_partition_by_id_or_name,
            partition.name,
            other_table,
        )

    def test_get_partition_by_device_name_and_number(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        factory.make_Partition(partition_table=partition_table)
        partition_two = factory.make_Partition(partition_table=partition_table)
        self.assertEqual(
            partition_two,
            Partition.objects.get_partition_by_device_name_and_number(
                block_device.get_name(), partition_two.get_partition_number()
            ),
        )

    def test_filter_by_tags_returns_partitions_with_one_tag(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        other_tags = [factory.make_name("tag") for _ in range(3)]
        partitions_with_tags = [
            factory.make_Partition(tags=tags) for _ in range(3)
        ]
        for _ in range(3):
            factory.make_Partition(tags=other_tags)
        self.assertItemsEqual(
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
        self.assertItemsEqual(
            partitions_with_tags, Partition.objects.filter_by_tags(tags)
        )

    def test_filter_by_tags_returns_no_devices(self):
        tags = [factory.make_name("tag") for _ in range(3)]
        for _ in range(3):
            factory.make_Partition(tags=tags)
        self.assertItemsEqual(
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
            for tag in tags:
                yield tag

        self.assertItemsEqual(
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
        block_device = factory.make_BlockDevice(size=3 * (1024 ** 4))  # 3TiB
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
        block_device = factory.make_BlockDevice(size=3 * (1024 ** 4))  # 3TiB
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.MBR
        )
        partition = partition_table.add_partition(size=1 * (1024 ** 4))
        partition.size = 2.5 * (1024 ** 4)
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
        block_device = factory.make_BlockDevice(size=3 * (1024 ** 4))  # 3TiB
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

    def test_get_partition_number_returns_starting_at_1_in_order_for_gpt(self):
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
        idx = 1
        for idx, partition in enumerate(partitions, 1):
            self.assertEqual(partition.get_partition_number(), idx)

    def test_get_partition_number_starting_at_2_for_amd64_not_uefi(self):
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
        for idx, partition in enumerate(partitions, 2):
            self.assertEqual(partition.get_partition_number(), idx)

    def test_get_partition_number_returns_starting_at_2_for_ppc64el(self):
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
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type=PARTITION_TABLE_TYPE.GPT
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(4)
        ]
        idx = 2
        for partition in partitions:
            self.expectThat(idx, Equals(partition.get_partition_number()))
            idx += 1

    def test_get_partition_number_returns_vmfs_order(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        pt = bd.get_partitiontable()
        self.assertItemsEqual(
            [1, 2, 3, 5, 6, 7, 8, 9],
            [part.get_partition_number() for part in pt.partitions.all()],
        )

    def test_get_partition_number_returns_starting_at_2_for_amd64_gpt(self):
        node = factory.make_Node(
            architecture="amd64/generic",
            bios_boot_method="pxe",
            with_boot_disk=False,
        )
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(
                (2 * (1024 ** 4))
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
        idx = 2
        for partition in partitions:
            self.expectThat(idx, Equals(partition.get_partition_number()))
            idx += 1

    def test_get_partition_number_returns_correct_numbering_for_mbr(self):
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
        idx = 1
        for partition in partitions:
            self.expectThat(idx, Equals(partition.get_partition_number()))
            idx += 1
            if idx == 4:
                # Skip the extended partition.
                idx += 1

    def test_is_vmfs_partition(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        pt = bd.get_partitiontable()
        for partition in pt.partitions.all():
            self.assertTrue(partition.is_vmfs_partition())

    def test_is_vmfs_partition_false_no_vmfs(self):
        partition = factory.make_Partition()
        self.assertFalse(partition.is_vmfs_partition())

    def test_is_vmfs_partition_false_different_block_device(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = VMFS6StorageLayout(node)
        layout.configure()
        other_bd_part = factory.make_Partition(node=node)
        self.assertFalse(other_bd_part.is_vmfs_partition())

    def test_is_vmfs_partition_false_extra_partition(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node, {"root_size": 10 * 1024 ** 3})
        layout.configure()
        pt = bd.get_partitiontable()
        extra_partition = pt.add_partition()
        self.assertFalse(extra_partition.is_vmfs_partition())

    def test_delete_not_allowed_if_part_of_filesystem_group(self):
        partition = factory.make_Partition(
            size=1024 ** 3, block_device_size=2 * 1024 ** 3
        )
        VolumeGroup.objects.create_volume_group(
            factory.make_name("vg"), [], [partition]
        )
        error = self.assertRaises(ValidationError, partition.delete)
        self.assertEqual(
            "Cannot delete partition because its part of a volume group.",
            error.message,
        )

    def test_delete_not_allowed_if_part_of_vmfs_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
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
        self.assertItemsEqual([tag], partition.tags)

    def test_add_tag_doesnt_duplicate(self):
        partition = Partition()
        tag = factory.make_name("tag")
        partition.add_tag(tag)
        partition.add_tag(tag)
        self.assertItemsEqual([tag], partition.tags)

    def test_remove_tag_deletes_tag(self):
        partition = Partition()
        tag = factory.make_name("tag")
        partition.add_tag(tag)
        partition.remove_tag(tag)
        self.assertItemsEqual([], partition.tags)
