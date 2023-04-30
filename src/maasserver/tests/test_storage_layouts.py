# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import json
from math import ceil
import random

from testtools.matchers import MatchesStructure

from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.filesystemgroup import VolumeGroup
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.models.partitiontable import (
    PARTITION_TABLE_EXTRA_SPACE,
    PREP_PARTITION_SIZE,
)
from maasserver.models.scriptset import ScriptSet
from maasserver.storage_layouts import (
    BcacheStorageLayout,
    BlankStorageLayout,
    calculate_size_from_percentage,
    CustomStorageLayout,
    EFI_PARTITION_SIZE,
    FlatStorageLayout,
    get_applied_storage_layout_for_node,
    get_storage_layout_for_node,
    is_percentage,
    LVMStorageLayout,
    MIN_BOOT_PARTITION_SIZE,
    MIN_ROOT_PARTITION_SIZE,
    STORAGE_LAYOUTS,
    StorageLayoutBase,
    StorageLayoutError,
    StorageLayoutFieldsError,
    StorageLayoutForm,
    StorageLayoutMissingBootDiskError,
    VMFS6StorageLayout,
    VMFS7StorageLayout,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block
from maastesting.matchers import MockCalledOnceWith
from metadataserver.builtin_scripts.tests import test_hooks
from metadataserver.enum import SCRIPT_TYPE
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)

LARGE_BLOCK_DEVICE = 100 * 1024 * 1024 * 1024  # 100 GiB

# exclude CustomStorageLayout since it can only be applied if storage config
# from commissioning data are availble
REGULAR_LAYOUTS = [
    layout_class
    for layout_class in STORAGE_LAYOUTS
    if layout_class is not CustomStorageLayout
]


def make_Node_with_uefi_boot_method(*args, **kwargs):
    kwargs["bios_boot_method"] = "uefi"
    kwargs["with_boot_disk"] = False
    return factory.make_Node(*args, **kwargs)


def make_ppc64el_Node_with_powernv_boot_method(*args, **kwargs):
    kwargs["bios_boot_method"] = "powernv"
    kwargs["with_boot_disk"] = False
    kwargs["architecture"] = "ppc64el/generic"
    return factory.make_Node(*args, **kwargs)


def make_ppc64el_Node_with_uefi_boot_method(*args, **kwargs):
    kwargs["bios_boot_method"] = "powerkvm"
    kwargs["with_boot_disk"] = False
    kwargs["architecture"] = "ppc64el/generic"
    return factory.make_Node(*args, **kwargs)


def make_arm64_Node_without_uefi_boot_method(*args, **kwargs):
    kwargs["bios_boot_method"] = "pxe"
    kwargs["with_boot_disk"] = False
    kwargs["architecture"] = "arm64/generic"
    return factory.make_Node(*args, **kwargs)


class TestFormHelpers(MAASServerTestCase):
    def test_get_storage_layout_for_node(self):
        node = make_Node_with_uefi_boot_method()
        layout = get_storage_layout_for_node("flat", node)
        self.assertIsInstance(layout, FlatStorageLayout)
        self.assertEqual(node, layout.node)


class TestGetAppliedStorageLayoutForNode(MAASServerTestCase):
    scenarios = [
        (layout_class.name, {"layout_class": layout_class})
        for layout_class in REGULAR_LAYOUTS
    ]

    def test_detects_layout(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = self.layout_class(node)
        layout.configure()
        self.assertEqual(
            (bd, self.layout_class.name),
            get_applied_storage_layout_for_node(node),
        )

    def test_returns_unknown(self):
        node = factory.make_Node()
        self.assertEqual(
            (None, "unknown"), get_applied_storage_layout_for_node(node)
        )


class TestStorageLayoutForm(MAASServerTestCase):
    def test_field_is_not_required(self):
        form = StorageLayoutForm(required=False, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_field_is_required(self):
        form = StorageLayoutForm(required=True, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {"storage_layout": ["This field is required."]}, form.errors
        )


class TestIsPercentageHelper(MAASServerTestCase):
    """Tests for `is_percentage`."""

    scenarios = [
        ("100%", {"value": "100%", "is_percentage": True}),
        ("10%", {"value": "10%", "is_percentage": True}),
        ("1.5%", {"value": "1.5%", "is_percentage": True}),
        ("1000.42%", {"value": "1000.42%", "is_percentage": True}),
        (
            "0.816112383915%",
            {"value": "0.816112383915%", "is_percentage": True},
        ),
        ("1000", {"value": "1000", "is_percentage": False}),
        ("10", {"value": "10", "is_percentage": False}),
        ("0", {"value": "0", "is_percentage": False}),
        ("int(0)", {"value": 0, "is_percentage": False}),
    ]

    def test_returns_correct_result(self):
        self.assertEqual(
            self.is_percentage,
            is_percentage(self.value),
            f"{self.value} gave incorrect result.",
        )


class TestCalculateSizeFromPercentHelper(MAASServerTestCase):
    """Tests for `calculate_size_from_percentage`."""

    scenarios = [
        ("100%", {"input": 10000, "percent": "100%", "output": 10000}),
        ("10%", {"input": 10000, "percent": "10%", "output": 1000}),
        ("1%", {"input": 10000, "percent": "1%", "output": 100}),
        (
            "5%",
            {"input": 4096, "percent": "5%", "output": int(ceil(4096 * 0.05))},
        ),
        (
            "0.816112383915%",
            {
                "input": 4096,
                "percent": "0.816112383915%",
                "output": int(ceil(4096 * 0.00816112383915)),
            },
        ),
    ]

    def test_returns_correct_result(self):
        self.assertEqual(
            self.output,
            calculate_size_from_percentage(self.input, self.percent),
            f"{self.percent} gave incorrect result.",
        )


class TestStorageLayoutBase(MAASServerTestCase):
    def test_init__sets_node(self):
        node = make_Node_with_uefi_boot_method()
        layout = StorageLayoutBase(node)
        self.assertEqual(node, layout.node)

    def test_init__loads_the_physical_block_devices(self):
        node = make_Node_with_uefi_boot_method()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        layout = StorageLayoutBase(node)
        self.assertEqual(block_devices, layout.block_devices)

    def test_raises_error_when_no_block_devices(self):
        node = make_Node_with_uefi_boot_method()
        layout = StorageLayoutBase(node)
        error = self.assertRaises(
            StorageLayoutMissingBootDiskError, layout.configure
        )
        self.assertEqual(
            "Node doesn't have any storage devices to configure.", str(error)
        )

    def test_raises_error_when_percentage_to_low_for_boot_disk(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {"boot_size": "0%"})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "boot_size": [
                    f"Size is too small. Minimum size is {MIN_BOOT_PARTITION_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_value_too_low_for_boot_disk(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(
            node, {"boot_size": MIN_BOOT_PARTITION_SIZE - 1}
        )
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "boot_size": [
                    f"Size is too small. Minimum size is {MIN_BOOT_PARTITION_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_percentage_too_high_for_boot_disk(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_ROOT_PARTITION_SIZE
        )
        to_high_percent = max_size / float(boot_disk.size)
        to_high_percent = f"{(to_high_percent + 1) * 100}%"
        layout = StorageLayoutBase(node, {"boot_size": to_high_percent})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"boot_size": [f"Size is too large. Maximum size is {max_size}."]},
            error.message_dict,
        )

    def test_raises_error_when_value_to_high_for_boot_disk(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_ROOT_PARTITION_SIZE
        )
        layout = StorageLayoutBase(node, {"boot_size": max_size + 1})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"boot_size": [f"Size is too large. Maximum size is {max_size}."]},
            error.message_dict,
        )

    def test_raises_error_when_percentage_to_low_for_root_disk(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {"root_size": "0%"})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "root_size": [
                    f"Size is too small. Minimum size is {MIN_ROOT_PARTITION_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_value_to_low_for_root_disk(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(
            node, {"root_size": MIN_ROOT_PARTITION_SIZE - 1}
        )
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "root_size": [
                    f"Size is too small. Minimum size is {MIN_ROOT_PARTITION_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_percentage_to_high_for_root_disk(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_BOOT_PARTITION_SIZE
        )
        to_high_percent = max_size / float(boot_disk.size)
        to_high_percent = f"{((to_high_percent + 1) * 100)}%"
        layout = StorageLayoutBase(node, {"root_size": to_high_percent})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"root_size": [f"Size is too large. Maximum size is {max_size}."]},
            error.message_dict,
        )

    def test_raises_error_when_value_to_high_for_root_disk(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        max_size = (
            boot_disk.size - EFI_PARTITION_SIZE - MIN_BOOT_PARTITION_SIZE
        )
        layout = StorageLayoutBase(node, {"root_size": max_size + 1})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"root_size": [f"Size is too large. Maximum size is {max_size}."]},
            error.message_dict,
        )

    def test_raises_error_when_boot_and_root_to_big(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(
            node, {"boot_size": "50%", "root_size": "60%"}
        )
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "__all__": [
                    "Size of the boot partition and root partition are larger "
                    "than the available space on the boot disk."
                ]
            },
            error.message_dict,
        )

    def test_doesnt_error_if_boot_and_root_valid(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(
            node, {"boot_size": "50%", "root_size": "50%"}
        )
        self.patch(StorageLayoutBase, "configure_storage")
        # This should not raise an exception.
        layout.configure()

    def test_get_boot_size_returns_0_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {"root_size": "50%"})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(0, layout.get_boot_size())

    def test_get_boot_size_returns_boot_size_if_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        boot_size = random.randint(
            MIN_BOOT_PARTITION_SIZE, MIN_BOOT_PARTITION_SIZE * 2
        )
        layout = StorageLayoutBase(node, {"boot_size": boot_size})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(boot_size, layout.get_boot_size())

    def test_get_root_device_returns_boot_disk_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(node.get_boot_disk(), layout.get_root_device())

    def test_get_root_device_returns_root_device_if_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        root_device = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = StorageLayoutBase(node, {"root_device": root_device.id})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(root_device, layout.get_root_device())

    def test_get_root_size_returns_None_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node, {})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertIsNone(layout.get_root_size())

    def test_get_root_size_returns_root_size_if_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = StorageLayoutBase(node, {"root_size": root_size})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(root_size, layout.get_root_size())

    def test_configure_calls_configure_storage(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = StorageLayoutBase(node)
        mock_configure_storage = self.patch(
            StorageLayoutBase, "configure_storage"
        )
        layout.configure()
        self.assertThat(mock_configure_storage, MockCalledOnceWith(True))

    def test_is_uefi_partition_detects_uefi_partition(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = StorageLayoutBase(node)
        self.assertTrue(layout.is_valid(), layout.errors)
        layout.create_basic_layout()
        pt = bd.get_partitiontable()
        self.assertTrue(layout.is_uefi_partition(pt.partitions.first()))

    def test_is_uefi_partition_returns_false_when_not(self):
        node = make_arm64_Node_without_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            layout = layout_class(node)
            layout.configure()
            for bd in node.physicalblockdevice_set.all():
                pt = bd.get_partitiontable()
                if pt is None:
                    continue
                for partition in pt.partitions.all():
                    self.assertFalse(
                        layout.is_uefi_partition(partition), layout_class.name
                    )

    def test_is_boot_partition(self):
        node = make_arm64_Node_without_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = StorageLayoutBase(node)
        self.assertTrue(layout.is_valid(), layout.errors)
        layout.create_basic_layout()
        pt = bd.get_partitiontable()
        self.assertTrue(layout.is_boot_partition(pt.partitions.first()))

    def test_is_boot_partition_returns_false_when_not(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            # Bcache always creates a boot partition.
            if layout_class == BcacheStorageLayout:
                continue
            layout = layout_class(node)
            layout.configure()
            for bd in node.physicalblockdevice_set.all():
                pt = bd.get_partitiontable()
                if pt is None:
                    continue
                for partition in pt.partitions.all():
                    self.assertFalse(
                        layout.is_boot_partition(partition), layout_class.name
                    )


class LayoutHelpersMixin:
    def assertEFIPartition(self, partition, boot_disk):
        self.assertIsNotNone(partition)
        self.assertEqual(
            round_size_to_nearest_block(
                EFI_PARTITION_SIZE, boot_disk.block_size
            ),
            partition.size,
        )
        self.assertThat(
            partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.FAT32,
                label="efi",
                mount_point="/boot/efi",
            ),
        )


class TestFlatStorageLayout(MAASServerTestCase, LayoutHelpersMixin):
    def test_init_sets_up_all_fields(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = FlatStorageLayout(node)
        self.assertEqual(
            {"root_device", "root_size", "boot_size"}, layout.fields.keys()
        )

    def test_creates_layout_with_gpt_defaults(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate root partition.
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[0]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_disk.size - PARTITION_TABLE_EXTRA_SPACE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_large_gpt_partition(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=3 * (1024**4)
        )
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate root partition.
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[0]
        self.assertIsNotNone(root_partition)
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_for_powernv(self):
        node = make_ppc64el_Node_with_powernv_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate root partition.
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[0]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_disk.size
                - PARTITION_TABLE_EXTRA_SPACE
                - PREP_PARTITION_SIZE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_for_powerkvm(self):
        node = make_ppc64el_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate root partition.
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[0]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_disk.size
                - PARTITION_TABLE_EXTRA_SPACE
                - PREP_PARTITION_SIZE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_uefi_defaults(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        partitions = partition_table.partitions.order_by("id").all()
        efi_partition = partitions[0]
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate root partition.
        root_partition = partitions[1]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_disk.size
                - EFI_PARTITION_SIZE
                - PARTITION_TABLE_EXTRA_SPACE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_for_arm64(self):
        node = make_arm64_Node_without_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate boot partition.
        partitions = partition_table.partitions.order_by("id").all()
        boot_partition = partitions[0]
        self.assertIsNotNone(boot_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                MIN_BOOT_PARTITION_SIZE, PARTITION_ALIGNMENT_SIZE, False
            ),
            boot_partition.size,
        )
        self.assertThat(
            boot_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="boot", mount_point="/boot"
            ),
        )

        # Validate root partition.
        root_partition = partitions[1]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_disk.size
                - EFI_PARTITION_SIZE
                - PARTITION_TABLE_EXTRA_SPACE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_boot_size(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        boot_size = random.randint(
            MIN_BOOT_PARTITION_SIZE, MIN_BOOT_PARTITION_SIZE * 2
        )
        layout = FlatStorageLayout(node, {"boot_size": boot_size})
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        partitions = partition_table.partitions.order_by("id").all()
        efi_partition = partitions[0]
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate boot partition.
        boot_partition = partitions[1]
        self.assertIsNotNone(boot_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_size, PARTITION_ALIGNMENT_SIZE, False
            ),
            boot_partition.size,
        )
        self.assertThat(
            boot_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="boot", mount_point="/boot"
            ),
        )

        # Validate root partition.
        root_partition = partitions[2]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_disk.size
                - boot_partition.size
                - EFI_PARTITION_SIZE
                - PARTITION_TABLE_EXTRA_SPACE,
                PARTITION_ALIGNMENT_SIZE,
                False,
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_root_size(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = FlatStorageLayout(node, {"root_size": root_size})
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        partitions = partition_table.partitions.order_by("id").all()
        efi_partition = partitions[0]
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate root partition.
        root_partition = partitions[1]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                root_size, PARTITION_ALIGNMENT_SIZE, False
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_boot_size_and_root_size(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        boot_size = random.randint(
            MIN_BOOT_PARTITION_SIZE, MIN_BOOT_PARTITION_SIZE * 2
        )
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = FlatStorageLayout(
            node, {"boot_size": boot_size, "root_size": root_size}
        )
        layout.configure()

        # Validate partition table.
        partition_table = boot_disk.get_partitiontable()
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

        # Validate efi partition.
        partitions = partition_table.partitions.order_by("id").all()
        efi_partition = partitions[0]
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate boot partition.
        boot_partition = partitions[1]
        self.assertIsNotNone(boot_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                boot_size, PARTITION_ALIGNMENT_SIZE, False
            ),
            boot_partition.size,
        )
        self.assertThat(
            boot_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="boot", mount_point="/boot"
            ),
        )

        # Validate root partition.
        root_partition = partitions[2]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                root_size, PARTITION_ALIGNMENT_SIZE, False
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_root_device_and_root_size(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        root_device = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = FlatStorageLayout(
            node, {"root_device": root_device.id, "root_size": root_size}
        )
        layout.configure()

        # Validate boot partition table.
        boot_partition_table = boot_disk.get_partitiontable()
        self.assertEqual(
            PARTITION_TABLE_TYPE.GPT, boot_partition_table.table_type
        )

        # Validate efi partition.
        boot_partitions = boot_partition_table.partitions.order_by("id").all()
        efi_partition = boot_partitions[0]
        self.assertEFIPartition(efi_partition, boot_disk)

        # Validate the root device partition table and partition.
        root_partition_table = root_device.get_partitiontable()
        self.assertEqual(
            PARTITION_TABLE_TYPE.GPT, boot_partition_table.table_type
        )
        root_partition = root_partition_table.partitions.order_by("id").all()[
            0
        ]
        self.assertIsNotNone(root_partition)
        self.assertEqual(
            round_size_to_nearest_block(
                root_size, PARTITION_ALIGNMENT_SIZE, False
            ),
            root_partition.size,
        )
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_is_layout_with_uefi(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_without_uefi(self):
        node = make_arm64_Node_without_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = FlatStorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_returns_none_when_not_found(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            if layout_class == FlatStorageLayout:
                continue
            layout = layout_class(node)
            layout.configure()
            flat_layout = FlatStorageLayout(node)
            self.assertIsNone(flat_layout.is_layout(), layout_class.name)


class TestLVMStorageLayout(MAASServerTestCase, LayoutHelpersMixin):
    def test_init_sets_up_all_fields(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(node)
        self.assertEqual(
            {
                "root_device",
                "root_size",
                "boot_size",
                "vg_name",
                "lv_name",
                "lv_size",
            },
            layout.fields.keys(),
        )

    def test_get_vg_name_returns_default_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(node, {})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(layout.DEFAULT_VG_NAME, layout.get_vg_name())

    def test_get_vg_name_returns_vg_name_if_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        vg_name = factory.make_name("vg")
        layout = LVMStorageLayout(node, {"vg_name": vg_name})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(vg_name, layout.get_vg_name())

    def test_get_lv_name_returns_default_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(node, {})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(layout.DEFAULT_LV_NAME, layout.get_lv_name())

    def test_get_lv_name_returns_lv_name_if_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        lv_name = factory.make_name("lv")
        layout = LVMStorageLayout(node, {"lv_name": lv_name})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(lv_name, layout.get_lv_name())

    def test_get_lv_size_returns_None_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(node, {})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertIsNone(layout.get_lv_size())

    def test_get_lv_size_returns_lv_size_if_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        lv_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = LVMStorageLayout(node, {"lv_size": lv_size})
        self.assertTrue(layout.is_valid(), layout.errors)
        self.assertEqual(lv_size, layout.get_lv_size())

    def test_get_calculated_lv_size_returns_set_lv_size(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        lv_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = LVMStorageLayout(node, {"lv_size": lv_size})
        self.assertTrue(layout.is_valid(), layout.errors)
        volume_group = factory.make_VolumeGroup(node=node)
        self.assertEqual(lv_size, layout.get_calculated_lv_size(volume_group))

    def test_get_calculated_lv_size_returns_size_of_volume_group(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(node, {})
        self.assertTrue(layout.is_valid(), layout.errors)
        volume_group = factory.make_VolumeGroup(node=node)
        self.assertEqual(
            volume_group.get_size(),
            layout.get_calculated_lv_size(volume_group),
        )

    def test_raises_error_when_percentage_to_low_for_logical_volume(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(node, {"lv_size": "0%"})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "lv_size": [
                    f"Size is too small. Minimum size is {MIN_ROOT_PARTITION_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_value_to_low_for_logical_volume(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = LVMStorageLayout(
            node, {"lv_size": MIN_ROOT_PARTITION_SIZE - 1}
        )
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "lv_size": [
                    f"Size is too small. Minimum size is {MIN_ROOT_PARTITION_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_percentage_to_high_for_logical_volume(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        root_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = LVMStorageLayout(
            node, {"root_size": root_size, "lv_size": "101%"}
        )
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"lv_size": [f"Size is too large. Maximum size is {root_size}."]},
            error.message_dict,
        )

    def test_raises_error_when_value_to_high_for_logical_volume(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        max_size = boot_disk.size - EFI_PARTITION_SIZE
        layout = LVMStorageLayout(node, {"lv_size": max_size + 1})
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"lv_size": [f"Size is too large. Maximum size is {max_size}."]},
            error.message_dict,
        )

    def test_creates_layout_with_defaults(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = LVMStorageLayout(node)
        layout.configure()

        # Validate the volume group on root partition.
        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[1]
        volume_group = VolumeGroup.objects.get(
            filesystems__partition=root_partition
        )
        self.assertIsNotNone(volume_group)
        self.assertEqual(layout.DEFAULT_VG_NAME, volume_group.name)

        # Validate one logical volume on volume group.
        self.assertEqual(
            1,
            volume_group.virtual_devices.count(),
            "Should have only 1 logical volume.",
        )
        logical_volume = volume_group.virtual_devices.first()
        self.assertEqual(volume_group.get_size(), logical_volume.size)
        self.assertEqual(layout.DEFAULT_LV_NAME, logical_volume.name)
        self.assertThat(
            logical_volume.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_vg_name_and_lv_name(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        vg_name = factory.make_name("vg")
        lv_name = factory.make_name("lv")
        layout = LVMStorageLayout(
            node, {"vg_name": vg_name, "lv_name": lv_name}
        )
        layout.configure()

        # Validate the volume group on root partition.
        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[1]
        volume_group = VolumeGroup.objects.get(
            filesystems__partition=root_partition
        )
        self.assertIsNotNone(volume_group)
        self.assertEqual(vg_name, volume_group.name)

        # Validate one logical volume on volume group.
        self.assertEqual(
            1,
            volume_group.virtual_devices.count(),
            "Should have only 1 logical volume.",
        )
        logical_volume = volume_group.virtual_devices.first()
        self.assertEqual(volume_group.get_size(), logical_volume.size)
        self.assertEqual(lv_name, logical_volume.name)
        self.assertThat(
            logical_volume.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_lv_size(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        lv_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout = LVMStorageLayout(node, {"lv_size": lv_size})
        layout.configure()

        # Validate the volume group on root partition.
        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[1]
        volume_group = VolumeGroup.objects.get(
            filesystems__partition=root_partition
        )
        self.assertIsNotNone(volume_group)
        self.assertEqual(layout.DEFAULT_VG_NAME, volume_group.name)

        # Validate one logical volume on volume group.
        self.assertEqual(
            1,
            volume_group.virtual_devices.count(),
            "Should have only 1 logical volume.",
        )
        logical_volume = volume_group.virtual_devices.first()
        expected_size = round_size_to_nearest_block(
            lv_size, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(expected_size, logical_volume.size)
        self.assertEqual(layout.DEFAULT_LV_NAME, logical_volume.name)
        self.assertThat(
            logical_volume.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_creates_layout_with_large_gpt_partition(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=7 * (1024**4)
        )
        layout = LVMStorageLayout(node)
        layout.configure()

        # Validate the volume group on root partition.
        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[0]
        volume_group = VolumeGroup.objects.get(
            filesystems__partition=root_partition
        )
        self.assertIsNotNone(volume_group)
        self.assertEqual(
            1, partition_table.partitions.count(), "Should have 1 partition."
        )
        self.assertEqual(PARTITION_TABLE_TYPE.GPT, partition_table.table_type)

    def test_is_layout_with_uefi(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = LVMStorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_without_uefi(self):
        node = make_arm64_Node_without_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = LVMStorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_returns_none_when_not_found(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            if layout_class == LVMStorageLayout:
                continue
            layout = layout_class(node)
            layout.configure()
            lvm_layout = LVMStorageLayout(node)
            self.assertIsNone(lvm_layout.is_layout(), layout_class.name)


class TestBcacheStorageLayout(MAASServerTestCase):
    def test_setup_cache_device_field_does_nothing_if_no_boot_device(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        layout.setup_cache_device_field()
        self.assertNotIn("cache_device", layout.fields)

    def test_setup_cache_device_field_doesnt_include_boot_device(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        other_disks = [
            factory.make_PhysicalBlockDevice(
                node=node, size=LARGE_BLOCK_DEVICE
            )
            for _ in range(3)
        ]
        valid_choices = [(disk.id, disk.id) for disk in other_disks]
        layout = BcacheStorageLayout(node)
        layout.setup_cache_device_field()
        self.assertEqual(valid_choices, layout.fields["cache_device"].choices)

    def test_find_best_cache_device_returns_None_if_not_boot_disk(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        self.assertIsNone(layout._find_best_cache_device())

    def test_find_best_cache_device_returns_smallest_ssd_first(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        # Small SSD
        factory.make_PhysicalBlockDevice(
            node=node, size=5 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        # Smallest SSD
        smallest_ssd = factory.make_PhysicalBlockDevice(
            node=node, size=2 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        # Very small not SSD
        factory.make_PhysicalBlockDevice(
            node=node, size=1 * 1024 * 1024 * 1024, tags=["rotary"]
        )
        layout = BcacheStorageLayout(node)
        self.assertEqual(smallest_ssd, layout._find_best_cache_device())

    def test_find_best_cache_device_returns_None_if_no_ssd(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        # Small Rotary
        factory.make_PhysicalBlockDevice(
            node=node, size=5 * 1024 * 1024 * 1024, tags=["rotary"]
        )
        # Smallest Rotary
        factory.make_PhysicalBlockDevice(
            node=node, size=2 * 1024 * 1024 * 1024, tags=["rotary"]
        )
        layout = BcacheStorageLayout(node)
        self.assertIsNone(layout._find_best_cache_device())

    def test_get_cache_device_returns_set_cache_device_over_find(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        # Small SSD
        small_ssd = factory.make_PhysicalBlockDevice(
            node=node, size=5 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        # Smallest SSD
        factory.make_PhysicalBlockDevice(
            node=node, size=2 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {"cache_device": small_ssd.id}
        self.assertEqual(small_ssd, layout.get_cache_device())

    def test_get_cache_device_returns_the_best_cache_device_if_not_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        # Small SSD
        factory.make_PhysicalBlockDevice(
            node=node, size=5 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        # Smallest SSD
        smallest_ssd = factory.make_PhysicalBlockDevice(
            node=node, size=2 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {}
        self.assertEqual(smallest_ssd, layout.get_cache_device())

    def test_get_cache_mode_returns_set_cache_mode(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        layout.cleaned_data = {"cache_mode": cache_mode}
        self.assertEqual(cache_mode, layout.get_cache_mode())

    def test_get_cache_mode_returns_default_if_blank(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {"cache_mode": ""}
        self.assertEqual(layout.DEFAULT_CACHE_MODE, layout.get_cache_mode())

    def test_get_cache_size_returns_set_cache_size(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        cache_size = random.randint(
            MIN_ROOT_PARTITION_SIZE, MIN_ROOT_PARTITION_SIZE * 2
        )
        layout.cleaned_data = {"cache_size": cache_size}
        self.assertEqual(cache_size, layout.get_cache_size())

    def test_get_cache_size_returns_None_if_blank(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {"cache_size": ""}
        self.assertIsNone(layout.get_cache_size())

    def test_get_cache_no_part_returns_boolean(self):
        node = make_Node_with_uefi_boot_method()
        layout = BcacheStorageLayout(node)
        cache_no_part = factory.pick_bool()
        layout.cleaned_data = {"cache_no_part": cache_no_part}
        self.assertEqual(cache_no_part, layout.get_cache_no_part())

    def test_create_cache_set_setups_up_cache_device_with_partition(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=5 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {"cache_no_part": False}
        cache_set = layout.create_cache_set()
        cache_device = cache_set.get_device()
        partition_table = ssd.get_partitiontable()
        self.assertIsNotNone(partition_table)
        partition = partition_table.partitions.order_by("id").all()[0]
        self.assertEqual(partition, cache_device)

    def test_create_cache_set_setups_up_cache_device_without_part(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=5 * 1024 * 1024 * 1024, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {"cache_no_part": True}
        cache_set = layout.create_cache_set()
        cache_device = cache_set.get_device()
        self.assertEqual(ssd, cache_device)

    def test_create_cache_set_setups_up_cache_device_with_cache_size(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        ssd = factory.make_PhysicalBlockDevice(
            node=node,
            size=5 * 1024 * 1024 * 1024,
            block_size=4096,
            tags=["ssd"],
        )
        cache_size = round_size_to_nearest_block(
            random.randint(3 * 1024 * 1024 * 1024, 4.5 * 1024 * 1024 * 1024),
            4096,
        )
        layout = BcacheStorageLayout(node)
        layout.cleaned_data = {
            "cache_size": cache_size,
            "cache_no_part": False,
        }
        cache_set = layout.create_cache_set()
        cache_device = cache_set.get_device()
        partition_table = ssd.get_partitiontable()
        self.assertIsNotNone(partition_table)
        partition = partition_table.partitions.order_by("id").all()[0]
        self.assertEqual(partition, cache_device)
        self.assertEqual(
            round_size_to_nearest_block(
                cache_size, PARTITION_ALIGNMENT_SIZE, False
            ),
            partition.size,
        )

    def test_raises_error_when_invalid_cache_device(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node, {"cache_device": boot_disk.id})
        layout.setup_cache_device_field()
        self.assertFalse(layout.is_valid(), layout.errors)
        self.assertEqual(
            {
                "cache_device": [
                    f"'{boot_disk.id}' is not a valid cache_device.  It should be one "
                    f"of: '{ssd.id}'."
                ]
            },
            layout.errors,
        )

    def test_raises_error_when_cache_size_and_cache_no_part_set(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = BcacheStorageLayout(
            node,
            {"cache_size": MIN_ROOT_PARTITION_SIZE, "cache_no_part": True},
        )
        layout.setup_cache_device_field()
        self.assertFalse(layout.is_valid(), layout.errors)
        self.assertEqual(
            {
                "cache_size": [
                    "Cannot use cache_size and cache_no_part at the same time."
                ],
                "cache_no_part": [
                    "Cannot use cache_size and cache_no_part at the same time."
                ],
            },
            layout.errors,
        )

    def test_raises_error_when_percentage_to_low_for_cache_size(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node, {"cache_size": "0%"})
        layout.setup_cache_device_field()
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "cache_size": [
                    f"Size is too small. Minimum size is {MIN_BLOCK_DEVICE_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_value_to_low_for_cache_size(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(
            node, {"cache_size": MIN_BLOCK_DEVICE_SIZE - 1}
        )
        layout.setup_cache_device_field()
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "cache_size": [
                    f"Size is too small. Minimum size is {MIN_BLOCK_DEVICE_SIZE}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_percentage_to_high_for_cache_size(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node, {"cache_size": "101%"})
        layout.setup_cache_device_field()
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "cache_size": [
                    f"Size is too large. Maximum size is {ssd.size}."
                ]
            },
            error.message_dict,
        )

    def test_raises_error_when_value_to_high_for_cache_size(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node, {"cache_size": ssd.size + 1})
        layout.setup_cache_device_field()
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {
                "cache_size": [
                    f"Size is too large. Maximum size is {ssd.size}."
                ]
            },
            error.message_dict,
        )

    def test_init_sets_up_cache_device_field(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = BcacheStorageLayout(node)
        self.assertIn("cache_device", layout.fields)

    def test_init_sets_up_all_fields(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = BcacheStorageLayout(node)
        self.assertEqual(
            {
                "root_device",
                "root_size",
                "boot_size",
                "cache_device",
                "cache_mode",
                "cache_size",
                "cache_no_part",
            },
            layout.fields.keys(),
        )

    def test_configure_storage_creates_flat_layout_if_no_cache_device(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = BcacheStorageLayout(node)
        layout.configure()

        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[1]
        self.assertIsNotNone(root_partition)
        self.assertThat(
            root_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_configure_creates_boot_partition(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.configure()

        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        boot_partition = partitions[1]
        self.assertEqual(1 * 1024**3, boot_partition.size)
        self.assertThat(
            boot_partition.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="boot", mount_point="/boot"
            ),
        )

    def test_configure_storage_creates_bcache_layout_with_ssd(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.configure()

        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[2]
        cache_partition_table = ssd.get_partitiontable()
        cache_partition = cache_partition_table.partitions.order_by(
            "id"
        ).all()[0]
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            root_partition.get_effective_filesystem().fstype,
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_CACHE,
            cache_partition.get_effective_filesystem().fstype,
        )
        root_filesystem = root_partition.get_effective_filesystem()
        self.assertEqual(
            FILESYSTEM_GROUP_TYPE.BCACHE,
            root_filesystem.filesystem_group.group_type,
        )
        cache_filesystem = cache_partition.get_effective_filesystem()
        self.assertEqual(
            root_filesystem.filesystem_group,
            cache_filesystem.cache_set.filesystemgroup_set.first(),
        )
        bcache = root_partition.get_effective_filesystem().filesystem_group
        self.assertIsNotNone(bcache)
        self.assertThat(
            bcache.virtual_device.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_configure_storage_creates_bcache_layout_without_partition(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node, {"cache_no_part": True})
        layout.configure()

        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[2]
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            root_partition.get_effective_filesystem().fstype,
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_CACHE, ssd.get_effective_filesystem().fstype
        )
        root_filesystem = root_partition.get_effective_filesystem()
        self.assertEqual(
            FILESYSTEM_GROUP_TYPE.BCACHE,
            root_filesystem.filesystem_group.group_type,
        )
        ssd_filesystem = ssd.get_effective_filesystem()
        self.assertEqual(
            root_partition.get_effective_filesystem().filesystem_group,
            ssd_filesystem.cache_set.filesystemgroup_set.first(),
        )
        bcache = root_partition.get_effective_filesystem().filesystem_group
        self.assertThat(
            bcache.virtual_device.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_configure_storage_creates_bcache_layout_with_cache_mode(self):
        node = make_Node_with_uefi_boot_method()
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        ssd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        cache_mode = factory.pick_enum(CACHE_MODE_TYPE)
        layout = BcacheStorageLayout(
            node, {"cache_no_part": True, "cache_mode": cache_mode}
        )
        layout.configure()

        partition_table = boot_disk.get_partitiontable()
        partitions = partition_table.partitions.order_by("id").all()
        root_partition = partitions[2]
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            root_partition.get_effective_filesystem().fstype,
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_CACHE, ssd.get_effective_filesystem().fstype
        )
        root_filesystem = root_partition.get_effective_filesystem()
        self.assertEqual(
            FILESYSTEM_GROUP_TYPE.BCACHE,
            root_filesystem.filesystem_group.group_type,
        )
        ssd_filesystem = ssd.get_effective_filesystem()
        self.assertEqual(
            root_partition.get_effective_filesystem().filesystem_group,
            ssd_filesystem.cache_set.filesystemgroup_set.first(),
        )
        bcache = root_partition.get_effective_filesystem().filesystem_group
        self.assertEqual(cache_mode, bcache.cache_mode)
        self.assertThat(
            bcache.virtual_device.get_effective_filesystem(),
            MatchesStructure.byEquality(
                fstype=FILESYSTEM_TYPE.EXT4, label="root", mount_point="/"
            ),
        )

    def test_is_layout_with_uefi(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_without_uefi(self):
        node = make_arm64_Node_without_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        layout = BcacheStorageLayout(node, {"cache_no_part": True})
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_returns_none_when_not_found(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            if layout_class == BcacheStorageLayout:
                continue
            layout = layout_class(node)
            layout.configure()
            bcache_layout = BcacheStorageLayout(node)
            self.assertIsNone(bcache_layout.is_layout(), layout_class.name)


class TestVMFS6StorageLayout(MAASServerTestCase):
    def test_init_sets_up_all_fields(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        layout = VMFS6StorageLayout(node)
        self.assertEqual(
            {"root_device", "root_size", "boot_size"}, layout.fields.keys()
        )

    def test_creates_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        self.assertEqual("vmfs6", layout.configure())
        pt = node.boot_disk.get_partitiontable()
        self.assertEqual(
            {
                f"{node.boot_disk.name}-part1": 3 * 1024**2,
                f"{node.boot_disk.name}-part2": 4 * 1024**3,
                f"{node.boot_disk.name}-part3": (
                    node.boot_disk.size
                    - 3 * 1024**2
                    - 4 * 1024**3
                    - 249 * 1024**2
                    - 249 * 1024**2
                    - 109 * 1024**2
                    - 285 * 1024**2
                    - 2560 * 1024**2
                    - 5 * 1024**2
                ),
                f"{node.boot_disk.name}-part5": 249 * 1024**2,
                f"{node.boot_disk.name}-part6": 249 * 1024**2,
                f"{node.boot_disk.name}-part7": 109 * 1024**2,
                f"{node.boot_disk.name}-part8": 285 * 1024**2,
                f"{node.boot_disk.name}-part9": 2560 * 1024**2,
            },
            {part.name: part.size for part in pt.partitions.all()},
        )

    def test_clean_validates_min_size(self):
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=10 * 1024**3 - 1
        )
        layout = VMFS6StorageLayout(node)
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"boot_size": ["Boot disk must be at least 10Gb."]},
            error.message_dict,
        )

    def test_accepts_root_device_param(self):
        # Regression test for LP:1825241
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        root_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node, {"root_device": root_disk.id})
        self.assertEqual("vmfs6", layout.configure())
        pt = root_disk.get_partitiontable()
        self.assertEqual(
            {
                f"{root_disk.name}-part1": 3 * 1024**2,
                f"{root_disk.name}-part2": 4 * 1024**3,
                f"{root_disk.name}-part3": (
                    root_disk.size
                    - 3 * 1024**2
                    - 4 * 1024**3
                    - 249 * 1024**2
                    - 249 * 1024**2
                    - 109 * 1024**2
                    - 285 * 1024**2
                    - 2560 * 1024**2
                    - 5 * 1024**2
                ),
                f"{root_disk.name}-part5": 249 * 1024**2,
                f"{root_disk.name}-part6": 249 * 1024**2,
                f"{root_disk.name}-part7": 109 * 1024**2,
                f"{root_disk.name}-part8": 285 * 1024**2,
                f"{root_disk.name}-part9": 2560 * 1024**2,
            },
            {part.name: part.size for part in pt.partitions.all()},
        )

    def test_accepts_root_size_param(self):
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node, {"root_size": 10 * 1024**3})
        self.assertEqual("vmfs6", layout.configure())
        pt = node.boot_disk.get_partitiontable()
        self.assertEqual(
            {
                f"{node.boot_disk.name}-part1": 3 * 1024**2,
                f"{node.boot_disk.name}-part2": 4 * 1024**3,
                f"{node.boot_disk.name}-part3": 10 * 1024**3,
                f"{node.boot_disk.name}-part5": 249 * 1024**2,
                f"{node.boot_disk.name}-part6": 249 * 1024**2,
                f"{node.boot_disk.name}-part7": 109 * 1024**2,
                f"{node.boot_disk.name}-part8": 285 * 1024**2,
                f"{node.boot_disk.name}-part9": 2560 * 1024**2,
            },
            {part.name: part.size for part in pt.partitions.all()},
        )

    def test_is_layout(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_without_datastore(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        # A user can delete the VMFS Datastore but the layout should still
        # be detected for the UI.
        node.virtualblockdevice_set.delete()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_returns_none_when_not_found(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            if layout_class == VMFS6StorageLayout:
                continue
            layout = layout_class(node)
            layout.configure()
            vmfs_layout = VMFS6StorageLayout(node)
            self.assertIsNone(vmfs_layout.is_layout(), layout_class.name)


class TestVMFS7StorageLayout(MAASServerTestCase):
    def gen_partition_map(self, disk, disk_size=None):
        dstore_size = disk_size or (
            disk.size
            - 100 * 1024**2
            - 4095 * 1024**2
            - 4095 * 1024**2
            - 25662832128
            - 8405504  # total rounding
        )
        return {
            f"{disk.name}-part1": 100 * 1024**2,
            f"{disk.name}-part5": 4095 * 1024**2,
            f"{disk.name}-part6": 4095 * 1024**2,
            f"{disk.name}-part7": 25662832128,
            f"{disk.name}-part8": dstore_size,
        }

    def test_init_sets_up_all_fields(self):
        node = factory.make_Node(with_boot_disk=False)
        layout = VMFS7StorageLayout(node)
        self.assertEqual(
            {"root_device", "root_size", "boot_size"}, layout.fields.keys()
        )

    def test_creates_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        self.assertEqual("vmfs7", layout.configure())
        pt = node.boot_disk.get_partitiontable()
        self.assertEqual(
            self.gen_partition_map(node.boot_disk),
            {part.name: part.size for part in pt.partitions.all()},
        )

    def test_clean_validates_min_size(self):
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=32 * 1024**3 - 1
        )
        layout = VMFS7StorageLayout(node)
        error = self.assertRaises(StorageLayoutFieldsError, layout.configure)
        self.assertEqual(
            {"boot_size": ["Boot disk must be at least 32Gb."]},
            error.message_dict,
        )

    def test_accepts_root_device_param(self):
        # Regression test for LP:1825241
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        root_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node, {"root_device": root_disk.id})
        self.assertEqual("vmfs7", layout.configure())
        pt = root_disk.get_partitiontable()
        self.assertEqual(
            self.gen_partition_map(root_disk),
            {part.name: part.size for part in pt.partitions.all()},
        )

    def test_accepts_root_size_param(self):
        node = factory.make_Node(with_boot_disk=False)
        node.boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node, {"root_size": 10 * 1024**3})
        self.assertEqual("vmfs7", layout.configure())
        pt = node.boot_disk.get_partitiontable()
        self.assertEqual(
            self.gen_partition_map(node.boot_disk, 10 * 1024**3),
            {part.name: part.size for part in pt.partitions.all()},
        )

    def test_is_layout(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_legacy(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout._default_layout = "legacy"
        layout.configure()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_without_datastore(self):
        node = make_Node_with_uefi_boot_method()
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        layout = VMFS7StorageLayout(node)
        layout.configure()
        # A user can delete the VMFS Datastore but the layout should still
        # be detected for the UI.
        node.virtualblockdevice_set.delete()
        self.assertEqual(bd, layout.is_layout())

    def test_is_layout_returns_none_when_not_found(self):
        node = make_Node_with_uefi_boot_method()
        factory.make_PhysicalBlockDevice(node=node, size=LARGE_BLOCK_DEVICE)
        factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE, tags=["ssd"]
        )
        for layout_class in REGULAR_LAYOUTS:
            if layout_class == VMFS7StorageLayout:
                continue
            layout = layout_class(node)
            layout.configure()
            vmfs_layout = VMFS7StorageLayout(node)
            self.assertIsNone(vmfs_layout.is_layout(), layout_class.name)


class TestBlankStorageLayout(MAASServerTestCase):
    scenarios = [
        (layout_class.name, {"layout_class": layout_class})
        for layout_class in REGULAR_LAYOUTS
    ]

    def test_creates_blank_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        bd = factory.make_PhysicalBlockDevice(
            node=node, size=LARGE_BLOCK_DEVICE
        )
        for _ in range(4):
            factory.make_PhysicalBlockDevice(
                node=node, size=LARGE_BLOCK_DEVICE
            )
        # Apply another layout to test clearing it
        other_layout = self.layout_class(node)
        other_layout.configure()

        layout = BlankStorageLayout(node)
        if self.layout_class != BlankStorageLayout:
            self.assertIsNone(layout.is_layout())
        self.assertEqual("blank", layout.configure())
        self.assertEqual(bd, layout.is_layout())
        self.assertFalse(node.virtualblockdevice_set.exists())
        for bd in node.current_config.blockdevice_set.all():
            self.assertFalse(bd.filesystem_set.exists())
            self.assertFalse(bd.partitiontable_set.exists())


class TestCustomStorageLayout(MAASServerTestCase):
    def test_creates_custom_layout(self):
        node = factory.make_Node(with_boot_disk=False)
        sda = factory.make_PhysicalBlockDevice(
            name="sda", node=node, size=LARGE_BLOCK_DEVICE
        )
        sdb = factory.make_PhysicalBlockDevice(
            name="sdb", node=node, size=LARGE_BLOCK_DEVICE
        )
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        script_set = ScriptSet.objects.create_commissioning_script_set(
            node,
            scripts=[lxd_script.name],
        )
        node.current_commissioning_script_set = script_set
        node.save()

        data = test_hooks.make_lxd_output()
        layout_data = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {"name": "sda1", "size": "200M", "fs": "vfat"},
                        {"name": "sda2", "size": "10G", "fs": "ext4"},
                    ],
                },
                "sdb": {
                    "type": "disk",
                    "ptable": "mbr",
                },
            },
            "mounts": {
                "/boot/efi": {
                    "device": "sda1",
                },
                "/": {
                    "device": "sda2",
                },
            },
        }
        data["storage-extra"] = layout_data
        output = json.dumps(data).encode()
        factory.make_ScriptResult(
            script_set=script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )

        layout = CustomStorageLayout(node)
        self.assertEqual(layout.configure(), "custom")
        ptable1 = sda.get_partitiontable()
        sda1, sda2 = ptable1.partitions.order_by("id")
        self.assertEqual(
            sda1.get_effective_filesystem().fstype, FILESYSTEM_TYPE.VFAT
        )
        self.assertEqual(
            sda2.get_effective_filesystem().fstype, FILESYSTEM_TYPE.EXT4
        )
        self.assertEqual(ptable1.table_type, PARTITION_TABLE_TYPE.GPT)
        ptable2 = sdb.get_partitiontable()
        self.assertEqual(ptable2.table_type, PARTITION_TABLE_TYPE.MBR)
        self.assertCountEqual(ptable2.partitions.all(), [])

    def test_creates_custom_layout_no_storage_data(self):
        node = factory.make_Node()
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        script_set = ScriptSet.objects.create_commissioning_script_set(
            node,
            scripts=[lxd_script.name],
        )
        node.current_commissioning_script_set = script_set
        node.save()

        output = json.dumps(test_hooks.make_lxd_output()).encode()
        factory.make_ScriptResult(
            script_set=script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )

        layout = CustomStorageLayout(node)
        error = self.assertRaises(StorageLayoutError, layout.configure)
        self.assertEqual(
            str(error), "No custom storage layout configuration found"
        )

    def test_creates_custom_layout_unappliable_layout(self):
        node = factory.make_Node()
        lxd_script = factory.make_Script(
            name=COMMISSIONING_OUTPUT_NAME,
            script_type=SCRIPT_TYPE.COMMISSIONING,
        )
        script_set = ScriptSet.objects.create_commissioning_script_set(
            node,
            scripts=[lxd_script.name],
        )
        node.current_commissioning_script_set = script_set
        node.save()

        data = test_hooks.make_lxd_output()
        # there is no "sda" disk
        layout_data = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {"name": "sda1", "size": "200M", "fs": "vfat"},
                        {"name": "sda2", "size": "10G", "fs": "ext4"},
                    ],
                },
            },
            "mounts": {
                "/boot/efi": {
                    "device": "sda1",
                },
                "/": {
                    "device": "sda2",
                },
            },
        }
        data["storage-extra"] = layout_data
        output = json.dumps(data).encode()
        factory.make_ScriptResult(
            script_set=script_set,
            script=lxd_script,
            exit_status=0,
            output=output,
            stdout=output,
        )

        layout = CustomStorageLayout(node)
        error = self.assertRaises(StorageLayoutError, layout.configure)
        self.assertEqual(
            str(error),
            "Failed to apply storage layout: Unknown machine disk(s): sda",
        )
