# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the storage layouts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from math import ceil
import random

from maasserver.enum import (
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.storage_layouts import (
    calculate_size_from_precentage,
    DEFAULT_BOOT_PARTITION_SIZE,
    EFI_PARTITION_SIZE,
    FlatStorageLayout,
    is_precentage,
    MIN_BOOT_PARTITION_SIZE,
    MIN_ROOT_PARTITION_SIZE,
    StorageLayoutBase,
    StorageLayoutFieldsError,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from testtools.matchers import MatchesStructure


LARGE_BLOCK_DEVICE = 10 * 1024 * 1024 * 1024  # 10 GiB


def round_size_by_blocks(size, block_size):
    number_of_blocks = size / block_size
    if size % block_size > 0:
        number_of_blocks += 1
    return number_of_blocks * block_size


class TestIsPrecentageHelper(MAASServerTestCase):
    """Tests for `is_precentage`."""

    scenarios = [
        ('100%', {
            'value': '100%',
            'is_precentage': True,
            }),
        ('10%', {
            'value': '10%',
            'is_precentage': True,
            }),
        ('1.5%', {
            'value': '1.5%',
            'is_precentage': True,
            }),
        ('1000.42%', {
            'value': '1000.42%',
            'is_precentage': True,
            }),
        ('0.816112383915%', {
            'value': '0.816112383915%',
            'is_precentage': True,
            }),
        ('1000', {
            'value': '1000',
            'is_precentage': False,
            }),
        ('10', {
            'value': '10',
            'is_precentage': False,
            }),
        ('0', {
            'value': '0',
            'is_precentage': False,
            }),
        ('int(0)', {
            'value': 0,
            'is_precentage': False,
            }),
    ]

    def test__returns_correct_result(self):
        self.assertEquals(
            self.is_precentage, is_precentage(self.value),
            "%s gave incorrect result." % self.value)


class TestCalculateSizeFromPrecentHelper(MAASServerTestCase):
    """Tests for `calculate_size_from_precentage`."""

    scenarios = [
        ('100%', {
            'input': 10000,
            'precent': '100%',
            'output': 10000,
            }),
        ('10%', {
            'input': 10000,
            'precent': '10%',
            'output': 1000,
            }),
        ('1%', {
            'input': 10000,
            'precent': '1%',
            'output': 100,
            }),
        ('5%', {
            'input': 4096,
            'precent': '5%',
            'output': int(ceil(4096 * .05)),
            }),
        ('0.816112383915%', {
            'input': 4096,
            'precent': '0.816112383915%',
            'output': int(ceil(4096 * 0.00816112383915)),
            }),
    ]

    def test__returns_correct_result(self):
        self.assertEquals(
            self.output,
            calculate_size_from_precentage(self.input, self.precent),
            "%s gave incorrect result." % self.precent)


class TestStorageLayoutBase(MAASServerTestCase):
    """Tests for `StorageLayoutBase`."""

    def test__init__sets_node(self):
        node = factory.make_Node()
        layout = StorageLayoutBase(node)
        self.assertEquals(node, layout.node)

    def test__init__loads_the_physical_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        layout = StorageLayoutBase(node)
        self.assertEquals(block_devices, layout.block_devices)

    def test_raises_error_when_no_block_devices(self):
        node = factory.make_Node()
        layout = StorageLayoutBase(node)
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "__all__": [
                "%s: doesn't have any storage devices to configure." % (
                    node.fqdn)],
            }, error.error_dict)

    def test_raises_error_when_precentage_to_low_for_boot_disk(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'boot_size': "0%",
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "boot_size": [
                "Size is too small. Minimum size is %s." % (
                    MIN_BOOT_PARTITION_SIZE)],
            }, error.error_dict)

    def test_raises_error_when_value_to_low_for_boot_disk(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'boot_size': MIN_BOOT_PARTITION_SIZE - 1,
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "boot_size": [
                "Size is too small. Minimum size is %s." % (
                    MIN_BOOT_PARTITION_SIZE)],
            }, error.error_dict)

    def test_raises_error_when_precentage_to_high_for_boot_disk(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_ROOT_PARTITION_SIZE)
        to_high_precent = max_size / float(boot_disk.size)
        to_high_precent = "%s%%" % ((to_high_precent + 1) * 100)
        layout = StorageLayoutBase(node, {
            'boot_size': to_high_precent,
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "boot_size": [
                "Size is too large. Maximum size is %s." % max_size],
            }, error.error_dict)

    def test_raises_error_when_value_to_high_for_boot_disk(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_ROOT_PARTITION_SIZE)
        layout = StorageLayoutBase(node, {
            'boot_size': max_size + 1,
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "boot_size": [
                "Size is too large. Maximum size is %s." % max_size],
            }, error.error_dict)

    def test_raises_error_when_precentage_to_low_for_root_disk(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'root_size': "0%",
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "root_size": [
                "Size is too small. Minimum size is %s." % (
                    MIN_ROOT_PARTITION_SIZE)],
            }, error.error_dict)

    def test_raises_error_when_value_to_low_for_root_disk(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'root_size': MIN_ROOT_PARTITION_SIZE - 1,
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "root_size": [
                "Size is too small. Minimum size is %s." % (
                    MIN_ROOT_PARTITION_SIZE)],
            }, error.error_dict)

    def test_raises_error_when_precentage_to_high_for_root_disk(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_BOOT_PARTITION_SIZE)
        to_high_precent = max_size / float(boot_disk.size)
        to_high_precent = "%s%%" % ((to_high_precent + 1) * 100)
        layout = StorageLayoutBase(node, {
            'root_size': to_high_precent,
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "root_size": [
                "Size is too large. Maximum size is %s." % max_size],
            }, error.error_dict)

    def test_raises_error_when_value_to_high_for_root_disk(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_BOOT_PARTITION_SIZE)
        layout = StorageLayoutBase(node, {
            'root_size': max_size + 1,
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "root_size": [
                "Size is too large. Maximum size is %s." % max_size],
            }, error.error_dict)

    def test_raises_error_when_boot_and_root_to_big(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'boot_size': "50%",
            'root_size': "60%",
            })
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEquals({
            "__all__": [
                "Size of the boot partition and root partition are larger "
                "than the available space on the boot disk."],
            }, error.error_dict)

    def test_doesnt_error_if_boot_and_root_valid(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'boot_size': "50%",
            'root_size': "50%",
            })
        self.patch(StorageLayoutBase, "configure_storage")
        # This should not raise an exception.
        layout.configure()

    def test_get_boot_size_returns_default_size_if_not_set(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            'root_size': "50%",
            })
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEquals(DEFAULT_BOOT_PARTITION_SIZE, layout.get_boot_size())

    def test_get_boot_size_returns_boot_size_if_set(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        boot_size = random.randint(
            MIN_BOOT_PARTITION_SIZE, MIN_BOOT_PARTITION_SIZE * 2)
        layout = StorageLayoutBase(node, {
            'boot_size': boot_size,
            })
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEquals(boot_size, layout.get_boot_size())

    def test_get_root_size_returns_None_if_not_set(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {
            })
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertIsNone(layout.get_root_size())

    def test_get_root_size_returns_root_size_if_set(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2)
        layout = StorageLayoutBase(node, {
            'root_size': root_size,
            })
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEquals(root_size, layout.get_root_size())

    def test_configure_calls_configure_storage(self):
        node = factory.make_Node()
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node)
        mock_configure_storage = self.patch(
            StorageLayoutBase, "configure_storage")
        layout.configure()
        self.assertThat(mock_configure_storage, MockCalledOnceWith())


class TestFlatStorageLayout(MAASServerTestCase):

    def assertEFIPartition(self, partition, boot_disk):
        self.assertIsNotNone(partition)
        self.assertEquals(
            round_size_by_blocks(EFI_PARTITION_SIZE, boot_disk.block_size),
            partition.size)
        self.assertThat(
            partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.FAT32,
                label="efi",
                mount_point="/boot/efi",
                ))

    def test__creates_layout_with_defaults(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEquals(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        efi_partition = partition_table.partitions.filter(
            partition_number=15).first()
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate boot partition.
        boot_partition = partition_table.partitions.filter(
            partition_number=1).first()
        self.assertIsNotNone(boot_partition)
        self.assertEquals(
            round_size_by_blocks(
                DEFAULT_BOOT_PARTITION_SIZE, boot_disk.block_size),
            boot_partition.size)
        self.assertThat(
            boot_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot",
                ))

        # Validate root partition.
        root_partition = partition_table.partitions.filter(
            partition_number=2).first()
        self.assertIsNotNone(root_partition)
        self.assertEquals(
            round_size_by_blocks(
                boot_disk.size - DEFAULT_BOOT_PARTITION_SIZE -
                EFI_PARTITION_SIZE, boot_disk.block_size),
            root_partition.size)
        self.assertThat(
            root_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="root",
                mount_point="/",
                ))

    def test__creates_layout_with_boot_size(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        boot_size = random.randint(
            MIN_BOOT_PARTITION_SIZE, MIN_BOOT_PARTITION_SIZE * 2)
        layout = FlatStorageLayout(node, {
            'boot_size': boot_size,
            })
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEquals(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        efi_partition = partition_table.partitions.filter(
            partition_number=15).first()
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate boot partition.
        boot_partition = partition_table.partitions.filter(
            partition_number=1).first()
        self.assertIsNotNone(boot_partition)
        self.assertEquals(
            round_size_by_blocks(
                boot_size, boot_disk.block_size),
            boot_partition.size)
        self.assertThat(
            boot_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot",
                ))

        # Validate root partition.
        root_partition = partition_table.partitions.filter(
            partition_number=2).first()
        self.assertIsNotNone(root_partition)
        self.assertEquals(
            round_size_by_blocks(
                boot_disk.size - boot_partition.size -
                EFI_PARTITION_SIZE, boot_disk.block_size),
            root_partition.size)
        self.assertThat(
            root_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="root",
                mount_point="/",
                ))

    def test__creates_layout_with_root_size(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2)
        layout = FlatStorageLayout(node, {
            'root_size': root_size,
            })
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEquals(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        efi_partition = partition_table.partitions.filter(
            partition_number=15).first()
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate boot partition.
        boot_partition = partition_table.partitions.filter(
            partition_number=1).first()
        self.assertIsNotNone(boot_partition)
        self.assertEquals(
            round_size_by_blocks(
                DEFAULT_BOOT_PARTITION_SIZE, boot_disk.block_size),
            boot_partition.size)
        self.assertThat(
            boot_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot",
                ))

        # Validate root partition.
        root_partition = partition_table.partitions.filter(
            partition_number=2).first()
        self.assertIsNotNone(root_partition)
        self.assertEquals(
            round_size_by_blocks(root_size, boot_disk.block_size),
            root_partition.size)
        self.assertThat(
            root_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="root",
                mount_point="/",
                ))

    def test__creates_layout_with_boot_size_and_root_size(self):
        node = factory.make_Node()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE)
        boot_size = random.randint(
            MIN_BOOT_PARTITION_SIZE, MIN_BOOT_PARTITION_SIZE * 2)
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2)
        layout = FlatStorageLayout(node, {
            'boot_size': boot_size,
            'root_size': root_size,
            })
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEquals(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        efi_partition = partition_table.partitions.filter(
            partition_number=15).first()
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate boot partition.
        boot_partition = partition_table.partitions.filter(
            partition_number=1).first()
        self.assertIsNotNone(boot_partition)
        self.assertEquals(
            round_size_by_blocks(
                boot_size, boot_disk.block_size),
            boot_partition.size)
        self.assertThat(
            boot_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="boot",
                mount_point="/boot",
                ))

        # Validate root partition.
        root_partition = partition_table.partitions.filter(
            partition_number=2).first()
        self.assertIsNotNone(root_partition)
        self.assertEquals(
            round_size_by_blocks(root_size, boot_disk.block_size),
            root_partition.size)
        self.assertThat(
            root_partition.filesystem, MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4,
                label="root",
                mount_point="/",
                ))
