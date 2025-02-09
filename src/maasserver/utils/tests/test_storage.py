# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for storage utilities."""

from maasserver.enum import (
    FILESYSTEM_GROUP_RAID_TYPE_CHOICES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    NODE_STATUS,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.storage import get_effective_filesystem, used_for


class TestGetEffectiveFilesystem(MAASServerTestCase):
    scenarios = (
        (
            "BlockDevice",
            {
                "factory": factory.make_BlockDevice,
                "filesystem_property": "block_device",
            },
        ),
        (
            "Partition",
            {
                "factory": factory.make_Partition,
                "filesystem_property": "partition",
            },
        ),
    )

    def test_returns_None_when_no_filesystem(self):
        model = self.factory()
        self.assertIsNone(get_effective_filesystem(model))

    def test_returns_filesystem_if_node_not_in_acquired_state(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        model = self.factory(node=node)
        filesystem = factory.make_Filesystem(
            **{self.filesystem_property: model}
        )
        self.assertEqual(filesystem, get_effective_filesystem(model))

    def test_returns_acquired_filesystem(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        model = self.factory(node=node)
        factory.make_Filesystem(**{self.filesystem_property: model})
        filesystem = factory.make_Filesystem(
            **{self.filesystem_property: model, "acquired": True}
        )
        self.assertEqual(filesystem, get_effective_filesystem(model))

    def test_returns_non_mountable_filesystem(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        model = self.factory(node=node)
        filesystem = factory.make_Filesystem(
            **{
                self.filesystem_property: model,
                "fstype": FILESYSTEM_TYPE.BCACHE_BACKING,
            }
        )
        self.assertEqual(filesystem, get_effective_filesystem(model))

    def test_returns_none_when_allocated_state(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        model = self.factory(node=node)
        factory.make_Filesystem(
            **{self.filesystem_property: model, "fstype": FILESYSTEM_TYPE.EXT4}
        )
        self.assertIsNone(get_effective_filesystem(model))


class TestUsedFor(MAASServerTestCase):
    def test_unused(self):
        block_device = factory.make_BlockDevice()
        self.assertEqual(used_for(block_device), "Unused")

    def test_fs_formatted(self):
        block_device = factory.make_BlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEqual(
            "Unmounted %s formatted filesystem" % fs.fstype,
            used_for(block_device),
        )

    def test_fs_formatted_and_mounted(self):
        block_device = factory.make_BlockDevice()
        fs = factory.make_Filesystem(
            block_device=block_device, mount_point="/mnt"
        )
        self.assertEqual(
            (
                "%s formatted filesystem mounted at %s"
                % (fs.fstype, fs.mount_point)
            ),
            used_for(block_device),
        )

    def test_partitioned(self):
        block_device = factory.make_BlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partitions = partition_table.partitions.count()
        if partitions > 1:
            expected_message = "%s partitioned with %d partitions"
        else:
            expected_message = "%s partitioned with %d partition"
        self.assertEqual(
            expected_message % (partition_table.table_type, partitions),
            used_for(block_device),
        )

    def test_lvm(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        self.assertEqual(
            ("LVM volume for %s" % filesystem_group.name),
            used_for(filesystem_group.filesystems.first().block_device),
        )

    def test_raid_active(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=factory.pick_choice(FILESYSTEM_GROUP_RAID_TYPE_CHOICES)
        )
        self.assertEqual(
            (
                "Active %s device for %s"
                % (filesystem_group.group_type, filesystem_group.name)
            ),
            used_for(filesystem_group.filesystems.first().block_device),
        )

    def test_raid_spare(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=factory.pick_choice(FILESYSTEM_GROUP_RAID_TYPE_CHOICES)
        )
        slave_block_device = factory.make_PhysicalBlockDevice()
        factory.make_Filesystem(
            block_device=slave_block_device,
            fstype=FILESYSTEM_TYPE.RAID_SPARE,
            filesystem_group=filesystem_group,
        )
        self.assertEqual(
            (
                "Spare %s device for %s"
                % (filesystem_group.group_type, filesystem_group.name)
            ),
            used_for(slave_block_device),
        )

    def test_bcache(self):
        cacheset = factory.make_CacheSet()
        blockdevice = cacheset.get_device()
        self.assertEqual(
            ("Cache device for %s" % cacheset.name), used_for(blockdevice)
        )

    def test_bcache_backing(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        self.assertEqual(
            ("Backing device for %s" % filesystem_group.name),
            used_for(filesystem_group.filesystems.first().block_device),
        )

    def test_vmfs(self):
        vmfs = factory.make_VMFS()
        part = vmfs.filesystems.first().partition
        self.assertEqual("VMFS extent for %s" % vmfs.name, used_for(part))
