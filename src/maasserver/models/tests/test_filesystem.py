# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Filesystem`."""


from copy import copy
from itertools import chain, combinations
import re
from uuid import uuid4

from django.core.exceptions import ValidationError
from testscenarios import multiply_scenarios
from testtools import ExpectedException
from testtools.matchers import Equals, Is, IsInstance, MatchesStructure

from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import RAID
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


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
            block_device=bd_for_partitions
        )
        partition = factory.make_Partition(partition_table=partition_table)
        filesystem_on_bd = factory.make_Filesystem(block_device=block_device)
        filesystem_on_partition = factory.make_Filesystem(partition=partition)
        filesystem_on_node = factory.make_Filesystem(node=node)
        self.assertItemsEqual(
            [
                root_fs,
                filesystem_on_bd,
                filesystem_on_partition,
                filesystem_on_node,
            ],
            Filesystem.objects.filter_by_node(node),
        )


class TestFilesystem(MAASServerTestCase):
    """Tests for the `Filesystem` model."""

    def test_get_node_returns_partition_node(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEqual(fs.partition.get_node(), fs.get_node())

    def test_get_node_returns_block_device_node(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(fs.block_device.node, fs.get_node())

    def test_get_node_returns_special_filesystem_node(self):
        machine = factory.make_Node()
        fs = factory.make_Filesystem(node=machine)
        self.assertEqual(machine, fs.get_node())

    def test_get_node_returns_None_when_no_substrate(self):
        fs = Filesystem()
        self.assertIsNone(fs.get_node())

    def test_get_physical_block_devices_single(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
        )
        self.assertEqual(
            filesystem.get_physical_block_devices(), [block_device]
        )

    def test_get_physical_block_devices_multiple(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
            )
            for block_device in block_devices
        ]
        fsgroup = factory.make_FilesystemGroup(
            node=node,
            filesystems=filesystems,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
        )
        virtual_block_device = factory.make_VirtualBlockDevice(
            filesystem_group=fsgroup
        )
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=virtual_block_device
        )
        self.assertEqual(
            filesystem.get_physical_block_devices(), block_devices
        )

    def test_get_physical_block_device_raid_on_part(self):
        # Regression test for LP:1849580
        node = factory.make_Node(with_boot_disk=False)
        block_devices = []
        partitions = []
        for _ in range(2):
            block_device = factory.make_PhysicalBlockDevice(node=node)
            block_devices.append(block_device)
            pt = factory.make_PartitionTable(block_device=block_device)
            partitions.append(
                factory.make_Partition(
                    partition_table=pt, size=pt.get_available_size()
                )
            )
        fs_group = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_1, partitions=partitions
        )
        fs = factory.make_Filesystem(block_device=fs_group.virtual_device)
        self.assertItemsEqual(fs.get_physical_block_devices(), block_devices)

    def test_get_size_returns_partition_size(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEqual(fs.partition.size, fs.get_size())

    def test_get_size_returns_block_device_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(fs.block_device.size, fs.get_size())

    def test_get_size_returns_0_when_partition_and_block_device_None(self):
        fs = Filesystem()
        self.assertEqual(0, fs.get_size())

    def test_get_block_size_returns_partition_block_size(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEqual(fs.partition.get_block_size(), fs.get_block_size())

    def test_get_block_size_returns_block_device_block_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(fs.block_device.block_size, fs.get_block_size())

    def test_get_block_size_returns_0_when_partition_and_device_None(self):
        fs = Filesystem()
        self.assertEqual(0, fs.get_block_size())

    def test_cannot_save_storage_backed_filesystem_if_storage_missing(self):
        fs = Filesystem()
        error = self.assertRaises(ValidationError, fs.save)
        self.assertThat(
            error.messages,
            Equals(["One of partition or block device must be specified."]),
        )

    def test_cannot_save_host_backed_filesystem_if_node_missing(self):
        for fstype in Filesystem.TYPES - Filesystem.TYPES_REQUIRING_STORAGE:
            fs = Filesystem(fstype=fstype)
            error = self.assertRaises(ValidationError, fs.save)
            self.expectThat(
                error.messages,
                Equals(["A node must be specified."]),
                "using " + fstype,
            )

    def test_cannot_save_filesystem_if_too_much_storage(self):
        substrate_factories = {
            "block_device": factory.make_BlockDevice,
            "partition": factory.make_Partition,
            "node": factory.make_Node,
        }
        substrate_combos = chain(
            combinations(substrate_factories, 2),
            combinations(substrate_factories, 3),
        )
        for substrates in substrate_combos:
            fs = Filesystem(
                **{
                    substrate: substrate_factories[substrate]()
                    for substrate in substrates
                }
            )
            error = self.assertRaises(ValidationError, fs.save)
            self.expectThat(
                error.messages,
                Equals(
                    [
                        "Only one of partition, block device, "
                        "or node can be specified."
                    ]
                ),
                "using " + ", ".join(substrates),
            )

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        fs = factory.make_Filesystem(uuid=uuid)
        self.assertEqual("%s" % uuid, fs.uuid)

    def test_get_parent_returns_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(block_device, filesystem.get_parent())

    def test_get_parent_returns_partition(self):
        partition = factory.make_Partition()
        filesystem = factory.make_Filesystem(partition=partition)
        self.assertEqual(partition, filesystem.get_parent())

    def test_get_parent_returns_special_filesystem_node(self):
        machine = factory.make_Node()
        filesystem = factory.make_Filesystem(node=machine)
        self.assertEqual(machine, filesystem.get_parent())

    def test_cannot_create_filesystem_directly_on_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        with ExpectedException(
            ValidationError,
            re.escape(
                "{'__all__': ['Cannot place filesystem directly on the "
                "boot disk. Create a partition on the boot disk first "
                "and then format the partition.']}"
            ),
        ):
            factory.make_Filesystem(block_device=boot_disk)

    def test_can_create_filesystem_on_partition_on_boot_disk(self):
        node = factory.make_Node(with_boot_disk=False)
        boot_disk = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=boot_disk)
        partition = factory.make_Partition(partition_table=partition_table)
        # Test is that an error is not raised.
        factory.make_Filesystem(partition=partition)

    def test_unique_on_partition_and_acquired(self):
        # For any given partition, at most one unacquired and one acquired
        # filesystem record may exist.
        partition = factory.make_Partition()
        filesystem = factory.make_Filesystem(partition=partition)
        self.assertIsNone(filesystem.block_device)

        # XXX: Why no Filesystem.acquire() method?
        filesystem_acquired = copy(filesystem)
        filesystem_acquired.id = None  # Force INSERT.
        filesystem_acquired.acquired = True
        filesystem_acquired.save()

        # Create a duplicate.
        filesystem_dupe = copy(filesystem)
        filesystem_dupe.id = None  # Force INSERT.

        error_messages_expected = Equals(
            ["Filesystem with this Partition and Acquired already exists."]
        )

        # Saving an unacquired duplicate fails.
        filesystem_dupe.acquired = False
        error = self.assertRaises(ValidationError, filesystem_dupe.save)
        self.assertThat(error.messages, error_messages_expected)

        # Saving an acquired duplicate fails.
        filesystem_dupe.acquired = True
        error = self.assertRaises(ValidationError, filesystem_dupe.save)
        self.assertThat(error.messages, error_messages_expected)

    def test_unique_on_block_device_and_acquired(self):
        # For any given block device, at most one unacquired and one acquired
        # filesystem record may exist.
        block_device = factory.make_BlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        self.assertIsNone(filesystem.partition)

        # XXX: Why no Filesystem.acquire() method?
        filesystem_acquired = copy(filesystem)
        filesystem_acquired.id = None  # Force INSERT.
        filesystem_acquired.acquired = True
        filesystem_acquired.save()

        # Create a duplicate.
        filesystem_dupe = copy(filesystem)
        filesystem_dupe.id = None  # Force INSERT.

        error_messages_expected = Equals(
            ["Filesystem with this Block device and Acquired already exists."]
        )

        # Saving an unacquired duplicate fails.
        filesystem_dupe.acquired = False
        error = self.assertRaises(ValidationError, filesystem_dupe.save)
        self.assertThat(error.messages, error_messages_expected)

        # Saving an acquired duplicate fails.
        filesystem_dupe.acquired = True
        error = self.assertRaises(ValidationError, filesystem_dupe.save)
        self.assertThat(error.messages, error_messages_expected)


class TestFilesystemMountableTypes(MAASServerTestCase):
    """Tests the `Filesystem` model with mountable filesystems."""

    scenarios_fstypes_with_storage = tuple(
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT.items()
        if name in Filesystem.TYPES_REQUIRING_STORAGE
    )

    scenarios_fstypes_without_storage = tuple(
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT.items()
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    )

    scenarios_substrate_storage = (
        (
            "partition",
            {
                "make_substrate": lambda: {
                    "partition": factory.make_Partition()
                },
                "can_be_unmounted": True,
            },
        ),
        (
            "block-device",
            {
                "make_substrate": lambda: {
                    "block_device": factory.make_PhysicalBlockDevice()
                },
                "can_be_unmounted": True,
            },
        ),
    )

    scenarios_substrate_node = (
        (
            "node",
            {
                "make_substrate": lambda: {"node": factory.make_Node()},
                "can_be_unmounted": False,
            },
        ),
    )

    scenarios = [
        *multiply_scenarios(
            scenarios_fstypes_with_storage, scenarios_substrate_storage
        ),
        *multiply_scenarios(
            scenarios_fstypes_without_storage, scenarios_substrate_node
        ),
    ]

    def test_can_create_mountable_filesystem(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(fstype=self.fstype, **substrate)
        self.assertThat(filesystem, IsInstance(Filesystem))
        self.assertThat(filesystem.fstype, Equals(self.fstype))
        self.assertThat(filesystem.is_mountable, Is(True))
        self.assertThat(filesystem, MatchesStructure.byEquality(**substrate))

    def test_cannot_mount_two_filesystems_at_same_point(self):
        substrate = self.make_substrate()
        filesystem1 = factory.make_Filesystem(fstype=self.fstype, **substrate)
        filesystem2 = factory.make_Filesystem(node=filesystem1.get_node())
        mount_point = factory.make_absolute_path()
        filesystem1.mount_point = mount_point
        filesystem1.save()
        filesystem2.mount_point = mount_point
        # Filesystems that can be mounted at a directory complain when mounted
        # at the same directory as another filesystem.
        if filesystem1.uses_mount_point:
            error = self.assertRaises(ValidationError, filesystem2.save)
            self.assertThat(
                error.messages,
                Equals(
                    [
                        "Another filesystem is already mounted at %s."
                        % mount_point
                    ]
                ),
            )
        else:
            self.assertThat(filesystem2.save(), Is(None))

    def test_can_mount_unacquired_and_acquired_filesystem_at_same_point(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(fstype=self.fstype, **substrate)
        filesystem.id = None
        filesystem.acquired = True
        self.assertThat(filesystem.save(), Is(None))

    def test_mount_point_is_none_for_filesystems_that_do_not_use_one(self):
        substrate = self.make_substrate()
        mount_point = factory.make_name("mount-point")
        filesystem = factory.make_Filesystem(
            fstype=self.fstype, mount_point=mount_point, **substrate
        )
        if filesystem.uses_mount_point:
            self.assertThat(filesystem.mount_point, Equals(mount_point))
        else:
            self.assertThat(filesystem.mount_point, Equals("none"))

    def test_filesystem_is_mounted_when_mount_point_is_set(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(fstype=self.fstype, **substrate)
        if self.can_be_unmounted:
            # Some filesystems can be unmounted. By default that's how the
            # factory makes them, so we need to set mount_point to see how
            # is_mounted behaves.
            self.assertThat(filesystem.is_mounted, Is(False))
            filesystem.mount_point = factory.make_name("path")
            self.assertThat(filesystem.is_mounted, Is(True))
        else:
            # Some filesystems cannot be unmounted, and the factory ensures
            # that they're always created with a mount point. We can unset
            # mount_point and observe a change in is_mounted, but we'll be
            # prevented from saving the amended filesystem.
            self.assertThat(filesystem.is_mounted, Is(True))
            filesystem.mount_point = None
            self.assertThat(filesystem.is_mounted, Is(False))
            error = self.assertRaises(ValidationError, filesystem.save)
            self.assertThat(
                error.messages,
                Equals(["RAM-backed filesystems must be mounted."]),
            )


class TestFilesystemsUsingMountPoints(MAASServerTestCase):
    """Tests the `Filesystem` model regarding use of mount points."""

    scenarios = tuple(
        (displayname, {"fstype": name, "mounts_at_path": (name != "swap")})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT.items()
    )

    def test_uses_mount_point_is_true_for_real_filesystems(self):
        filesystem = factory.make_Filesystem(fstype=self.fstype)
        self.assertThat(
            filesystem.uses_mount_point, Equals(self.mounts_at_path)
        )


class TestFilesystemsUsingStorage(MAASServerTestCase):
    """Tests the `Filesystem` model regarding use of storage."""

    scenarios = tuple(
        (
            displayname,
            {
                "fstype": name,
                "mounts_device_or_partition": (
                    name != "ramfs" and name != "tmpfs"
                ),
            },
        )
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT.items()
    )

    def test_uses_mount_point_is_true_for_real_filesystems(self):
        filesystem = factory.make_Filesystem(fstype=self.fstype)
        self.assertThat(
            filesystem.uses_storage, Equals(self.mounts_device_or_partition)
        )
