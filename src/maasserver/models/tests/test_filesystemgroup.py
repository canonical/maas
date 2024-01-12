# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
import re
from unittest import skip
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404

from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_RAID_TYPES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    PARTITION_TABLE_TYPE,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import (
    Bcache,
    BcacheManager,
    FilesystemGroup,
    LVM_PE_SIZE,
    RAID,
    RAID_SUPERBLOCK_OVERHEAD,
    RAIDManager,
    VMFS,
    VolumeGroup,
    VolumeGroupManager,
)
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_objects
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import (
    machine_readable_bytes,
    round_size_to_nearest_block,
)
from maasserver.utils.orm import reload_object


class TestManagersGetObjectOr404(MAASServerTestCase):
    """Tests for the `get_object_or_404` on the managers."""

    scenarios = (
        ("FilesystemGroup", {"model": FilesystemGroup, "type": None}),
        (
            "VolumeGroup",
            {"model": VolumeGroup, "type": FILESYSTEM_GROUP_TYPE.LVM_VG},
        ),
        ("RAID", {"model": RAID, "type": FILESYSTEM_GROUP_TYPE.RAID_0}),
        ("Bcache", {"model": Bcache, "type": FILESYSTEM_GROUP_TYPE.BCACHE}),
    )

    def test_raises_Http404_when_invalid_node(self):
        user = factory.make_admin()
        filesystem_group = factory.make_FilesystemGroup(group_type=self.type)
        self.assertRaises(
            Http404,
            self.model.objects.get_object_or_404,
            factory.make_name("system_id"),
            filesystem_group.id,
            user,
            NodePermission.view,
        )

    def test_raises_Http404_when_invalid_device(self):
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertRaises(
            Http404,
            self.model.objects.get_object_or_404,
            node.system_id,
            random.randint(0, 100),
            user,
            NodePermission.view,
        )

    def test_view_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertRaises(
            PermissionDenied,
            self.model.objects.get_object_or_404,
            node.system_id,
            filesystem_group.id,
            user,
            NodePermission.view,
        )

    def test_view_returns_device_by_name(self):
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertEqual(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id,
                filesystem_group.name,
                user,
                NodePermission.view,
            ).id,
        )

    def test_view_returns_device_when_no_owner(self):
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertEqual(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user, NodePermission.view
            ).id,
        )

    def test_view_returns_device_when_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertEqual(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user, NodePermission.view
            ).id,
        )

    def test_edit_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertRaises(
            PermissionDenied,
            self.model.objects.get_object_or_404,
            node.system_id,
            filesystem_group.id,
            user,
            NodePermission.edit,
        )

    def test_edit_returns_device_when_user_is_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertEqual(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user, NodePermission.edit
            ).id,
        )

    def test_admin_raises_PermissionDenied_when_user_requests_admin(self):
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertRaises(
            PermissionDenied,
            self.model.objects.get_object_or_404,
            node.system_id,
            filesystem_group.id,
            user,
            NodePermission.admin,
        )

    def test_admin_returns_device_when_admin(self):
        user = factory.make_admin()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type
        )
        self.assertEqual(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user, NodePermission.admin
            ).id,
        )


class TestManagersFilterByBlockDevice(MAASServerTestCase):
    """Tests for the managers `filter_by_block_device`."""

    def test_volume_group_on_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem]
        )
        filesystem_groups = VolumeGroup.objects.filter_by_block_device(
            block_device
        )
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_volume_group_on_partition(self):
        block_device = factory.make_PhysicalBlockDevice(size=10 * 1024**3)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(
            size=5 * 1024**3, partition_table=partition_table
        )
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem]
        )
        filesystem_groups = VolumeGroup.objects.filter_by_block_device(
            block_device
        )
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_volume_group_on_two_partitions(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition_one = factory.make_Partition(partition_table=partition_table)
        partition_two = factory.make_Partition(partition_table=partition_table)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_one
        )
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_one, filesystem_two],
        )
        filesystem_groups = VolumeGroup.objects.filter_by_block_device(
            block_device
        )
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_raid_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_one
        )
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two],
        )
        filesystem_groups = RAID.objects.filter_by_block_device(
            block_device_one
        )
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_raid_on_partitions(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition_one = factory.make_Partition(partition_table=partition_table)
        partition_two = factory.make_Partition(partition_table=partition_table)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_one
        )
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two],
        )
        filesystem_groups = RAID.objects.filter_by_block_device(block_device)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_bcache_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=block_device_one)
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_backing = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            block_device=block_device_two,
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            cache_set=cache_set,
            filesystems=[filesystem_backing],
        )
        filesystem_groups = Bcache.objects.filter_by_block_device(
            block_device_one
        )
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_bcache_on_partitions(self):
        device_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE * 4, MIN_BLOCK_DEVICE_SIZE * 1024
        )
        block_device = factory.make_PhysicalBlockDevice(
            size=device_size + PARTITION_TABLE_EXTRA_SPACE
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition_one = factory.make_Partition(
            partition_table=partition_table, size=device_size // 2
        )
        partition_two = factory.make_Partition(
            partition_table=partition_table, size=device_size // 2
        )
        cache_set = factory.make_CacheSet(partition=partition_one)
        filesystem_backing = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING, partition=partition_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            cache_set=cache_set,
            filesystems=[filesystem_backing],
        )
        filesystem_groups = Bcache.objects.filter_by_block_device(block_device)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)


class TestManagersFilterByNode(MAASServerTestCase):
    """Tests for the managers `filter_by_node`."""

    def test_volume_group_on_block_device(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem]
        )
        filesystem_groups = VolumeGroup.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_volume_group_on_partition(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem]
        )
        filesystem_groups = VolumeGroup.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_volume_group_on_two_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition_one = factory.make_Partition(partition_table=partition_table)
        partition_two = factory.make_Partition(partition_table=partition_table)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_one
        )
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_one, filesystem_two],
        )
        filesystem_groups = VolumeGroup.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_raid_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_one
        )
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two],
        )
        filesystem_groups = RAID.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_raid_on_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition_one = factory.make_Partition(partition_table=partition_table)
        partition_two = factory.make_Partition(partition_table=partition_table)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_one
        )
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two],
        )
        filesystem_groups = RAID.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_bcache_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        cache_set = factory.make_CacheSet(block_device=block_device_one)
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_backing = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            block_device=block_device_two,
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            cache_set=cache_set,
            filesystems=[filesystem_backing],
        )
        filesystem_groups = Bcache.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)

    def test_bcache_on_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition_one = factory.make_Partition(partition_table=partition_table)
        partition_two = factory.make_Partition(partition_table=partition_table)
        cache_set = factory.make_CacheSet(partition=partition_one)
        filesystem_backing = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING, partition=partition_two
        )
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            cache_set=cache_set,
            filesystems=[filesystem_backing],
        )
        filesystem_groups = Bcache.objects.filter_by_node(node)
        result_filesystem_group_ids = [
            fsgroup.id for fsgroup in filesystem_groups
        ]
        self.assertEqual([filesystem_group.id], result_filesystem_group_ids)


class TestFilesystemGroupManager(MAASServerTestCase):
    """Tests for the `FilesystemGroupManager`."""

    def test_get_available_name_for_returns_next_idx(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        filesystem_group.save()
        prefix = filesystem_group.get_name_prefix()
        current_idx = int(filesystem_group.name.replace(prefix, ""))
        self.assertEqual(
            f"{prefix}{current_idx + 1}",
            FilesystemGroup.objects.get_available_name_for(filesystem_group),
        )

    def test_get_available_name_for_ignores_bad_int(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        filesystem_group.save()
        prefix = filesystem_group.get_name_prefix()
        filesystem_group.name = "{}{}".format(prefix, factory.make_name("bad"))
        filesystem_group.save()
        self.assertEqual(
            "%s0" % prefix,
            FilesystemGroup.objects.get_available_name_for(filesystem_group),
        )


class TestVolumeGroupManager(MAASServerTestCase):
    """Tests for the `VolumeGroupManager`."""

    def test_create_volume_group_with_name_and_uuid(self):
        block_device = factory.make_PhysicalBlockDevice()
        name = factory.make_name("vg")
        vguuid = "%s" % uuid4()
        volume_group = VolumeGroup.objects.create_volume_group(
            name, [block_device], [], uuid=vguuid
        )
        self.assertEqual(name, volume_group.name)
        self.assertEqual(vguuid, volume_group.uuid)

    def test_create_volume_group_with_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        name = factory.make_name("vg")
        volume_group = VolumeGroup.objects.create_volume_group(
            name, block_devices, []
        )
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(block_devices, block_devices_in_vg)

    def test_create_volume_group_with_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_BLOCK_DEVICE_SIZE * 3) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        name = factory.make_name("vg")
        volume_group = VolumeGroup.objects.create_volume_group(
            name, [], partitions
        )
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertCountEqual(partitions, partitions_in_vg)

    def test_create_volume_group_with_block_devices_and_partitions(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_BLOCK_DEVICE_SIZE * 3) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        name = factory.make_name("vg")
        volume_group = VolumeGroup.objects.create_volume_group(
            name, block_devices, partitions
        )
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
            if filesystem.block_device is not None
        ]
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
            if filesystem.partition is not None
        ]
        self.assertCountEqual(block_devices, block_devices_in_vg)
        self.assertCountEqual(partitions, partitions_in_vg)


class TestFilesystemGroup(MAASServerTestCase):
    """Tests for the `FilesystemGroup` model."""

    def test_virtual_device_raises_AttributeError_for_lvm(self):
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        with self.assertRaisesRegex(
            AttributeError, "should not be called when group_type = LVM_VG"
        ):
            fsgroup.virtual_device

    def test_virtual_device_returns_VirtualBlockDevice_for_group(self):
        fsgroup = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            )
        )
        self.assertEqual(
            VirtualBlockDevice.objects.get(filesystem_group=fsgroup),
            fsgroup.virtual_device,
        )

    def test_get_numa_node_indexes_all_same(self):
        fsgroup = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.VMFS6]
            )
        )
        self.assertEqual(fsgroup.get_numa_node_indexes(), [0])

    def test_get_numa_node_indexes_multiple(self):
        node = factory.make_Node()
        numa_nodes = [
            node.default_numanode,
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
        ]
        block_devices = [
            factory.make_PhysicalBlockDevice(numa_node=numa_node)
            for numa_node in numa_nodes
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
        self.assertEqual(fsgroup.get_numa_node_indexes(), [0, 1, 2])

    def test_get_numa_node_indexes_nested(self):
        node = factory.make_Node()
        numa_nodes = [
            node.default_numanode,
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
        ]
        # 2 physical disks have filesystems on them directly
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(
                    numa_node=numa_node
                ),
            )
            for numa_node in numa_nodes[:2]
        ]

        # the 3 remaining disks are part of another filesystem group which gets
        # added to the first
        nested_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(
                    numa_node=numa_node
                ),
            )
            for numa_node in numa_nodes[2:]
        ]
        nested_group = factory.make_FilesystemGroup(
            node=node,
            filesystems=nested_filesystems,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
        )
        virtual_block_device = factory.make_VirtualBlockDevice(
            filesystem_group=nested_group
        )
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=virtual_block_device,
            )
        )

        fsgroup = factory.make_FilesystemGroup(
            node=node,
            filesystems=filesystems,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
        )
        self.assertEqual(fsgroup.get_numa_node_indexes(), [0, 1, 2, 3, 4])

    def test_get_node_returns_first_filesystem_node(self):
        fsgroup = factory.make_FilesystemGroup()
        self.assertEqual(
            fsgroup.filesystems.first().get_node(), fsgroup.get_node()
        )

    def test_get_node_returns_None_if_no_filesystems(self):
        fsgroup = FilesystemGroup()
        self.assertIsNone(fsgroup.get_node())

    def test_get_size_returns_0_if_lvm_without_filesystems(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertEqual(0, fsgroup.get_size())

    def test_get_size_returns_sum_of_all_filesystem_sizes_for_lvm(self):
        node = factory.make_Node()
        block_size = 4096
        total_size = 0
        filesystems = []
        for _ in range(3):
            size = random.randint(
                MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
            )
            total_size += size
            block_device = factory.make_PhysicalBlockDevice(
                node=node, size=size, block_size=block_size
            )
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
                )
            )
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=filesystems
        )
        # Reserve one extent per filesystem for LVM headers.
        extents = (total_size // LVM_PE_SIZE) - 3
        self.assertEqual(extents * LVM_PE_SIZE, fsgroup.get_size())

    def test_get_size_returns_0_if_raid_without_filesystems(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.RAID_0)
        self.assertEqual(0, fsgroup.get_size())

    def test_get_size_returns_sum_of_disk_size_for_raid_0(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
        )
        large_size = random.randint(small_size + 1, small_size + (10**5))
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size
                ),
            ),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=large_size
                ),
            ),
        ]
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0, filesystems=filesystems
        )
        self.assertEqual(
            fsgroup.get_size(),
            (small_size + large_size) - RAID_SUPERBLOCK_OVERHEAD * 2,
        )

    def test_get_size_returns_smallest_disk_size_for_raid_1(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
        )
        large_size = random.randint(small_size + 1, small_size + (10**5))
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size
                ),
            ),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=large_size
                ),
            ),
        ]
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_1, filesystems=filesystems
        )
        self.assertEqual(
            small_size - RAID_SUPERBLOCK_OVERHEAD, fsgroup.get_size()
        )

    def test_get_size_returns_correct_disk_size_for_raid_5(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
        )
        other_size = random.randint(small_size + 1, small_size + (10**5))
        number_of_raid_devices = random.randint(2, 9)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size
                ),
            )
        ]
        for _ in range(number_of_raid_devices):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size
                    ),
                )
            )
        # Spares are ignored and not taken into calculation.
        for _ in range(3):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size
                    ),
                )
            )
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5, filesystems=filesystems
        )
        self.assertEqual(
            (small_size * number_of_raid_devices) - RAID_SUPERBLOCK_OVERHEAD,
            fsgroup.get_size(),
        )

    def test_get_size_returns_correct_disk_size_for_raid_6(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
        )
        other_size = random.randint(small_size + 1, small_size + (10**5))
        number_of_raid_devices = random.randint(3, 9)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size
                ),
            )
        ]
        for _ in range(number_of_raid_devices):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size
                    ),
                )
            )
        # Spares are ignored and not taken into calculation.
        for _ in range(3):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size
                    ),
                )
            )
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_6, filesystems=filesystems
        )
        self.assertEqual(
            (small_size * (number_of_raid_devices - 1))
            - RAID_SUPERBLOCK_OVERHEAD,
            fsgroup.get_size(),
        )

    @skip("XXX: GavinPanella 2015-12-04 bug=1522965: Fails spuriously.")
    def test_get_size_returns_correct_disk_size_for_raid_10(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
        )
        other_size = random.randint(small_size + 1, small_size + (10**5))
        number_of_raid_devices = random.randint(3, 9)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size
                ),
            )
        ]
        for _ in range(number_of_raid_devices):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size
                    ),
                )
            )
        # Spares are ignored and not taken into calculation.
        for _ in range(3):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size
                    ),
                )
            )
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_10, filesystems=filesystems
        )
        self.assertEqual(
            (small_size * (number_of_raid_devices + 1) // 2)
            - RAID_SUPERBLOCK_OVERHEAD,
            fsgroup.get_size(),
        )

    def test_get_size_returns_0_if_bcache_without_backing(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        self.assertEqual(0, fsgroup.get_size())

    def test_get_size_returns_size_of_backing_device_with_bcache(self):
        node = factory.make_Node()
        backing_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE**2
        )
        cache_set = factory.make_CacheSet(node=node)
        backing_block_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=backing_block_device,
            )
        ]
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            cache_set=cache_set,
            filesystems=filesystems,
        )
        self.assertEqual(backing_size, fsgroup.get_size())

    def test_get_size_returns_total_size_with_vmfs(self):
        vmfs = factory.make_VMFS()
        self.assertEqual(vmfs.get_total_size(), vmfs.get_size())

    def test_get_total_size(self):
        vmfs = factory.make_VMFS()
        size = 0
        for fs in vmfs.filesystems.all():
            size += fs.get_size()
        self.assertEqual(size, vmfs.get_total_size())

    def test_is_lvm_returns_true_when_LVM_VG(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertTrue(fsgroup.is_lvm())

    def test_is_lvm_returns_false_when_not_LVM_VG(self):
        fsgroup = FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            )
        )
        self.assertFalse(fsgroup.is_lvm())

    def test_is_raid_returns_true_for_all_raid_types(self):
        fsgroup = FilesystemGroup()
        for raid_type in FILESYSTEM_GROUP_RAID_TYPES:
            fsgroup.group_type = raid_type
            self.assertTrue(
                fsgroup.is_raid(),
                "is_raid should return true for %s" % raid_type,
            )

    def test_is_raid_returns_false_for_LVM_VG(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertFalse(fsgroup.is_raid())

    def test_is_raid_returns_false_for_BCACHE(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        self.assertFalse(fsgroup.is_raid())

    def test_is_bcache_returns_true_when_BCACHE(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        self.assertTrue(fsgroup.is_bcache())

    def test_is_bcache_returns_false_when_not_BCACHE(self):
        fsgroup = FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.BCACHE]
            )
        )
        self.assertFalse(fsgroup.is_bcache())

    def test_is_vmfs(self):
        vmfs = factory.make_VMFS()
        self.assertTrue(vmfs.is_vmfs())

    def test_creating_vmfs_automatically_creates_mounted_fs(self):
        part = factory.make_Partition()
        name = factory.make_name("datastore")
        vmfs = VMFS.objects.create_vmfs(name, [part])
        self.assertEqual(
            "/vmfs/volumes/%s" % name,
            vmfs.virtual_device.get_effective_filesystem().mount_point,
        )

    def test_can_save_new_filesystem_group_without_filesystems(self):
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"),
        )
        fsgroup.save()
        self.assertIsNotNone(fsgroup.id)
        self.assertEqual(fsgroup.filesystems.count(), 0)

    def test_cannot_save_without_filesystems(self):
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"),
        )
        fsgroup.save()
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['At least one filesystem must have "
                "been added.']}"
            ),
        ):
            fsgroup.save(force_update=True)

    def test_cannot_save_without_filesystems_from_different_nodes(self):
        filesystems = [factory.make_Filesystem(), factory.make_Filesystem()]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['All added filesystems must belong to "
                "the same node.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
                filesystems=filesystems,
            )

    def test_cannot_save_volume_group_if_invalid_filesystem(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            ),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            ),
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Volume group can only contain lvm "
                "physical volumes.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
                filesystems=filesystems,
            )

    def test_can_save_volume_group_if_valid_filesystems(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            ),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            ),
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=filesystems
        )

    def test_cannot_save_volume_group_if_logical_volumes_larger(self):
        node = factory.make_Node()
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=factory.make_PhysicalBlockDevice(node=node),
        )
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=factory.make_PhysicalBlockDevice(node=node),
        )
        filesystems = [filesystem_one, filesystem_two]
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=filesystems
        )
        factory.make_VirtualBlockDevice(
            size=volume_group.get_size(), filesystem_group=volume_group
        )
        filesystem_two.delete()
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "['Volume group cannot be smaller than its "
                "logical volumes.']"
            ),
        ):
            volume_group.save()

    def test_cannot_save_raid_0_with_less_than_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 0 must have at least 2 raid "
                "devices and no spares.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
                filesystems=filesystems,
            )

    def test_cannot_save_raid_0_with_spare_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(2)
        ]
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 0 must have at least 2 raid "
                "devices and no spares.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
                filesystems=filesystems,
            )

    def test_can_save_raid_0_with_exactly_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(2)
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0, filesystems=filesystems
        )

    def test_can_save_raid_0_with_more_then_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(10)
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0, filesystems=filesystems
        )

    def test_cannot_save_raid_1_with_less_than_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 1 must have at least 2 raid "
                "devices and any number of spares.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_1,
                filesystems=filesystems,
            )

    def test_can_save_raid_1_with_spare_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(2)
        ]
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
        )
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_1, filesystems=filesystems
        )

    def test_can_save_raid_1_with_2_or_more_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(2, 10))
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_1, filesystems=filesystems
        )

    def test_cannot_save_raid_5_with_less_than_3_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(1, 2))
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 5 must have at least 3 raid "
                "devices and any number of spares.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_5,
                filesystems=filesystems,
            )

    def test_can_save_raid_5_with_3_or_more_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(3, 10))
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node),
                )
            )
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5, filesystems=filesystems
        )

    def test_cannot_save_raid_6_with_less_than_4_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(1, 3))
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 6 must have at least 4 raid "
                "devices and any number of spares.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_6,
                filesystems=filesystems,
            )

    def test_can_save_raid_6_with_4_or_more_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(4, 10))
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node),
                )
            )
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_6, filesystems=filesystems
        )

    def test_cannot_save_raid_10_with_less_than_3_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(1, 2))
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 10 must have at least 3 raid "
                "devices and any number of spares.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_10,
                filesystems=filesystems,
            )

    def test_can_save_raid_10_with_3_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(3)
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node),
                )
            )
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_10, filesystems=filesystems
        )

    def test_can_save_raid_10_with_4_or_more_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(4, 10))
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node),
                )
            )
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_10, filesystems=filesystems
        )

    def test_cannot_save_bcache_without_cache_set(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Bcache requires an assigned cache set.']}"
            ),
        ):
            filesystem_group = factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=filesystems,
            )
            filesystem_group.cache_set = None
            filesystem_group.save()

    def test_cannot_save_bcache_without_backing(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['At least one filesystem must have "
                "been added.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                cache_set=cache_set,
                filesystems=[],
            )

    def test_cannot_save_bcache_with_logical_volume_as_backing(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_VirtualBlockDevice(node=node),
            )
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Bcache cannot use a logical volume as a "
                "backing device.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                cache_set=cache_set,
                filesystems=filesystems,
            )

    def test_can_save_bcache_with_cache_set_and_backing(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_set=cache_set,
            filesystems=filesystems,
        )

    def test_cannot_save_bcache_with_multiple_backings(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node),
            )
            for _ in range(random.randint(2, 10))
        ]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Bcache can only contain one backing "
                "device.']}"
            ),
        ):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                cache_set=cache_set,
                filesystems=filesystems,
            )

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        fsgroup = factory.make_FilesystemGroup(uuid=uuid)
        self.assertEqual("%s" % uuid, fsgroup.uuid)

    def test_save_calls_create_or_update_for_when_filesystems_linked(self):
        mock_create_or_update_for = self.patch(
            VirtualBlockDevice.objects, "create_or_update_for"
        )
        filesystem_group = factory.make_FilesystemGroup()
        mock_create_or_update_for.assert_called_once_with(filesystem_group)

    def test_save_doesnt_call_create_or_update_for_when_no_filesystems(self):
        mock_create_or_update_for = self.patch(
            VirtualBlockDevice.objects, "create_or_update_for"
        )
        filesystem_group = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"),
        )
        filesystem_group.save()
        mock_create_or_update_for.assert_not_called()

    def test_get_lvm_allocated_size_and_get_lvm_free_space(self):
        """Check get_lvm_allocated_size and get_lvm_free_space methods."""
        backing_volume_size = machine_readable_bytes("10G")
        node = factory.make_Node()
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"),
        )
        fsgroup.save()
        block_size = 4096
        for i in range(5):
            block_device = factory.make_BlockDevice(
                node=node, size=backing_volume_size, block_size=block_size
            )
            factory.make_Filesystem(
                filesystem_group=fsgroup,
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=block_device,
            )
        # Size should be 50 GB minus one extent per filesystem for LVM headers.
        pv_total_size = 50 * 1000**3
        extents = (pv_total_size // LVM_PE_SIZE) - 5
        usable_size = extents * LVM_PE_SIZE
        self.assertEqual(usable_size, fsgroup.get_size())

        # Allocate two VirtualBlockDevice's
        factory.make_VirtualBlockDevice(
            filesystem_group=fsgroup, size=35 * 1000**3
        )
        factory.make_VirtualBlockDevice(
            filesystem_group=fsgroup, size=5 * 1000**3
        )

        expected_size = round_size_to_nearest_block(
            40 * 1000**3, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(expected_size, fsgroup.get_lvm_allocated_size())
        self.assertEqual(
            usable_size - expected_size, fsgroup.get_lvm_free_space()
        )

    def test_get_virtual_block_device_block_size_returns_backing_for_bc(self):
        # This test is not included in the scenario below
        # `TestFilesystemGroupGetVirtualBlockDeviceBlockSize` because it has
        # different logic that doesn't fit in the scenario.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        filesystem = filesystem_group.get_bcache_backing_filesystem()
        self.assertEqual(
            filesystem.get_block_size(),
            filesystem_group.get_virtual_block_device_block_size(),
        )

    def test_delete_deletes_filesystems_not_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=bd
            )
            for bd in block_devices
        ]
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=filesystems
        )
        filesystem_group.delete()
        deleted_filesystems = reload_objects(Filesystem, filesystems)
        kept_block_devices = reload_objects(PhysicalBlockDevice, block_devices)
        self.assertCountEqual([], deleted_filesystems)
        self.assertCountEqual(block_devices, kept_block_devices)

    def test_delete_deletes_lvm_without_lvs_on_raid(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        raid = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_0,
            block_devices=block_devices,
        )
        VolumeGroup.objects.create_volume_group(
            factory.make_name(),
            block_devices=[raid.virtual_device],
            partitions=[],
        )
        raid.delete()
        self.assertIsNone(reload_object(raid))

    def test_delete_cannot_delete_volume_group_with_logical_volumes(self):
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        factory.make_VirtualBlockDevice(
            size=volume_group.get_size(), filesystem_group=volume_group
        )
        error = self.assertRaises(ValidationError, volume_group.delete)
        self.assertEqual(
            "This volume group has logical volumes; it cannot be deleted.",
            error.message,
        )

    def test_delete_deletes_virtual_block_device(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            )
        )
        virtual_device = filesystem_group.virtual_device
        filesystem_group.delete()
        self.assertIsNone(
            reload_object(virtual_device),
            "VirtualBlockDevice should have been deleted.",
        )


class TestFilesystemGroupGetNiceName(MAASServerTestCase):
    scenarios = [
        (
            FILESYSTEM_GROUP_TYPE.LVM_VG,
            {
                "group_type": FILESYSTEM_GROUP_TYPE.LVM_VG,
                "name": "volume group",
            },
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_0,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_0, "name": "RAID"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_1,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_1, "name": "RAID"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_5,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_5, "name": "RAID"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_6,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_6, "name": "RAID"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_10,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_10, "name": "RAID"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.BCACHE,
            {"group_type": FILESYSTEM_GROUP_TYPE.BCACHE, "name": "Bcache"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.VMFS6,
            {"group_type": FILESYSTEM_GROUP_TYPE.VMFS6, "name": "VMFS"},
        ),
    ]

    def test_returns_prefix(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=self.group_type
        )
        self.assertEqual(self.name, filesystem_group.get_nice_name())


class TestFilesystemGroupGetNamePrefix(MAASServerTestCase):
    scenarios = [
        (
            FILESYSTEM_GROUP_TYPE.LVM_VG,
            {"group_type": FILESYSTEM_GROUP_TYPE.LVM_VG, "prefix": "vg"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_0,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_0, "prefix": "md"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_1,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_1, "prefix": "md"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_5,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_5, "prefix": "md"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_6,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_6, "prefix": "md"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_10,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_10, "prefix": "md"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.BCACHE,
            {"group_type": FILESYSTEM_GROUP_TYPE.BCACHE, "prefix": "bcache"},
        ),
        (
            FILESYSTEM_GROUP_TYPE.VMFS6,
            {"group_type": FILESYSTEM_GROUP_TYPE.VMFS6, "prefix": "vmfs"},
        ),
    ]

    def test_returns_prefix(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=self.group_type
        )
        self.assertEqual(self.prefix, filesystem_group.get_name_prefix())


class TestFilesystemGroupGetVirtualBlockDeviceBlockSize(MAASServerTestCase):
    scenarios = [
        (
            FILESYSTEM_GROUP_TYPE.LVM_VG,
            {"group_type": FILESYSTEM_GROUP_TYPE.LVM_VG, "block_size": 4096},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_0,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_0, "block_size": 512},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_1,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_1, "block_size": 512},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_5,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_5, "block_size": 512},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_6,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_6, "block_size": 512},
        ),
        (
            FILESYSTEM_GROUP_TYPE.RAID_10,
            {"group_type": FILESYSTEM_GROUP_TYPE.RAID_10, "block_size": 512},
        ),
        (
            FILESYSTEM_GROUP_TYPE.VMFS6,
            {"group_type": FILESYSTEM_GROUP_TYPE.VMFS6, "block_size": 1024},
        ),
        # For BCACHE see
        # `test_get_virtual_block_device_block_size_returns_backing_for_bc`
        # above.
    ]

    def test_returns_block_size(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=self.group_type
        )
        self.assertEqual(
            self.block_size,
            filesystem_group.get_virtual_block_device_block_size(),
        )


class TestVolumeGroup(MAASServerTestCase):
    def test_objects_is_VolumeGroupManager(self):
        self.assertIsInstance(VolumeGroup.objects, VolumeGroupManager)

    def test_group_type_set_to_LVM_VG(self):
        obj = VolumeGroup()
        self.assertEqual(FILESYSTEM_GROUP_TYPE.LVM_VG, obj.group_type)

    def test_update_block_devices_and_partitions(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        new_block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_BLOCK_DEVICE_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=partition_block_device
        )
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        new_partition = partition_table.add_partition(
            size=MIN_BLOCK_DEVICE_SIZE
        )
        initial_bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=bd
            )
            for bd in block_devices
        ]
        initial_part_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, partition=part
            )
            for part in partitions
        ]
        volume_group = factory.make_VolumeGroup(
            filesystems=initial_bd_filesystems + initial_part_filesystems
        )
        deleted_block_device = block_devices[0]
        updated_block_devices = [new_block_device] + block_devices[1:]
        deleted_partition = partitions[0]
        update_partitions = [new_partition] + partitions[1:]
        volume_group.update_block_devices_and_partitions(
            updated_block_devices, update_partitions
        )
        self.assertIsNone(deleted_block_device.get_effective_filesystem())
        self.assertIsNone(deleted_partition.get_effective_filesystem())
        self.assertEqual(
            volume_group.id,
            new_block_device.get_effective_filesystem().filesystem_group.id,
        )
        self.assertEqual(
            volume_group.id,
            new_partition.get_effective_filesystem().filesystem_group.id,
        )
        for device in block_devices[1:] + partitions[1:]:
            self.assertEqual(
                volume_group.id,
                device.get_effective_filesystem().filesystem_group.id,
            )

    def test_create_logical_volume(self):
        volume_group = factory.make_VolumeGroup()
        name = factory.make_name()
        vguuid = "%s" % uuid4()
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, volume_group.get_size())
        logical_volume = volume_group.create_logical_volume(
            name=name, uuid=vguuid, size=size
        )
        logical_volume = reload_object(logical_volume)
        expected_size = round_size_to_nearest_block(
            size, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(logical_volume.name, name)
        self.assertEqual(logical_volume.uuid, vguuid)
        self.assertEqual(logical_volume.size, expected_size)
        self.assertEqual(
            logical_volume.block_size,
            volume_group.get_virtual_block_device_block_size(),
        )


class TestRAID(MAASServerTestCase):
    def test_objects_is_RAIDManager(self):
        self.assertIsInstance(RAID.objects, RAIDManager)

    def test_init_raises_ValueError_if_group_type_not_set_to_raid_type(self):
        self.assertRaises(
            ValueError, RAID, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )

    def test_create_raid(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        for bd in block_devices[5:]:
            factory.make_PartitionTable(block_device=bd)
        partitions = [
            bd.get_partitiontable().add_partition() for bd in block_devices[5:]
        ]
        spare_block_device = block_devices[0]
        spare_partition = partitions[0]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
            uuid=uuid,
            block_devices=block_devices[1:5],
            partitions=partitions[1:],
            spare_devices=[spare_block_device],
            spare_partitions=[spare_partition],
        )
        self.assertEqual("md0", raid.name)
        self.assertEqual(
            (6 * partitions[1].size) - RAID_SUPERBLOCK_OVERHEAD,
            raid.get_size(),
        )
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_6, raid.group_type)
        self.assertEqual(uuid, raid.uuid)
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(
            8, raid.filesystems.filter(fstype=FILESYSTEM_TYPE.RAID).count()
        )
        self.assertEqual(
            2,
            raid.filesystems.filter(fstype=FILESYSTEM_TYPE.RAID_SPARE).count(),
        )

    def test_create_raid_0_with_a_spare_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 0 must have at least 2 raid "
                "devices and no spares.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_0,
                uuid=uuid,
                block_devices=block_devices[1:],
                partitions=[],
                spare_devices=block_devices[:1],
                spare_partitions=[],
            )

    def test_create_raid_without_devices_fails(self):
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['At least one filesystem must have been "
                "added.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_0,
                uuid=uuid,
                block_devices=[],
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_create_raid_0_with_one_element_fails(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 0 must have at least 2 raid "
                "devices and no spares.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_0,
                uuid=uuid,
                block_devices=[block_device],
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_create_raid_1_with_spares(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        for bd in block_devices[5:]:
            factory.make_PartitionTable(block_device=bd)
        partitions = [
            bd.get_partitiontable().add_partition() for bd in block_devices[5:]
        ]
        # Partition size will be smaller than the disk, because of overhead.
        spare_block_device = block_devices[0]
        spare_partition = partitions[0]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
            uuid=uuid,
            block_devices=block_devices[1:5],
            partitions=partitions[1:],
            spare_devices=[spare_block_device],
            spare_partitions=[spare_partition],
        )
        self.assertEqual("md0", raid.name)
        self.assertEqual(
            partitions[1].size - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_1, raid.group_type)
        self.assertEqual(uuid, raid.uuid)
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(
            8, raid.filesystems.filter(fstype=FILESYSTEM_TYPE.RAID).count()
        )
        self.assertEqual(
            2,
            raid.filesystems.filter(fstype=FILESYSTEM_TYPE.RAID_SPARE).count(),
        )

    def test_create_raid_1_with_one_element_fails(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 1 must have at least 2 raid "
                "devices and any number of spares.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_1,
                uuid=uuid,
                block_devices=[block_device],
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_create_raid_5_with_spares(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        for bd in block_devices[5:]:
            factory.make_PartitionTable(block_device=bd)
        partitions = [
            bd.get_partitiontable().add_partition() for bd in block_devices[5:]
        ]
        spare_block_device = block_devices[0]
        spare_partition = partitions[0]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices[1:5],
            partitions=partitions[1:],
            spare_devices=[spare_block_device],
            spare_partitions=[spare_partition],
        )
        self.assertEqual("md0", raid.name)
        self.assertEqual(
            (7 * partitions[1].size) - RAID_SUPERBLOCK_OVERHEAD,
            raid.get_size(),
        )
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_5, raid.group_type)
        self.assertEqual(uuid, raid.uuid)
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(
            8, raid.filesystems.filter(fstype=FILESYSTEM_TYPE.RAID).count()
        )
        self.assertEqual(
            2,
            raid.filesystems.filter(fstype=FILESYSTEM_TYPE.RAID_SPARE).count(),
        )

    def test_create_raid_5_with_2_elements_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for _ in range(2)
        ]
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 5 must have at least 3 raid "
                "devices and any number of spares.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_5,
                uuid=uuid,
                block_devices=block_devices,
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_create_raid_6_with_3_elements_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 6 must have at least 4 raid "
                "devices and any number of spares.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_6,
                uuid=uuid,
                block_devices=block_devices,
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_create_raid_10_with_2_elements_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(2)
        ]
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 10 must have at least 3 raid "
                "devices and any number of spares.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_10,
                uuid=uuid,
                block_devices=block_devices,
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_create_raid_with_block_device_from_other_node_fails(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        block_devices_1 = [
            factory.make_PhysicalBlockDevice(node=node1) for _ in range(5)
        ]
        block_devices_2 = [
            factory.make_PhysicalBlockDevice(node=node2) for _ in range(5)
        ]
        uuid = str(uuid4())
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['All added filesystems must belong to the "
                "same node.']}"
            ),
        ):
            RAID.objects.create_raid(
                name="md0",
                level=FILESYSTEM_GROUP_TYPE.RAID_1,
                uuid=uuid,
                block_devices=block_devices_1 + block_devices_2,
                partitions=[],
                spare_devices=[],
                spare_partitions=[],
            )

    def test_add_device_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        device = factory.make_PhysicalBlockDevice(node=node, size=device_size)
        raid.add_device(device, FILESYSTEM_TYPE.RAID)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(
            (10 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_add_spare_device_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        device = factory.make_PhysicalBlockDevice(node=node, size=device_size)
        raid.add_device(device, FILESYSTEM_TYPE.RAID_SPARE)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(
            (9 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_add_partition_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=device_size
            )
        ).add_partition()
        raid.add_partition(partition, FILESYSTEM_TYPE.RAID)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(
            (10 * partition.size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_add_spare_partition_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=device_size
            )
        ).add_partition()
        raid.add_partition(partition, FILESYSTEM_TYPE.RAID_SPARE)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(
            (9 * partition.size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_add_device_from_another_node_to_array_fails(self):
        node = factory.make_Node()
        other_node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        device = factory.make_PhysicalBlockDevice(
            node=other_node, size=device_size
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "['Device needs to be attached to the same node config as "
                "the rest of the array.']"
            ),
        ):
            raid.add_device(device, FILESYSTEM_TYPE.RAID)
        self.assertEqual(10, raid.filesystems.count())  # Still 10 devices
        self.assertEqual(
            (9 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_add_partition_from_another_node_to_array_fails(self):
        node = factory.make_Node()
        other_node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=other_node, size=device_size
            )
        ).add_partition()
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "['Partition must be on a device from the same node as "
                "the rest of the array.']"
            ),
        ):
            raid.add_partition(partition, FILESYSTEM_TYPE.RAID)
        self.assertEqual(10, raid.filesystems.count())  # Nothing added
        self.assertEqual(
            (9 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_add_already_used_device_to_array_fails(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        device = factory.make_PhysicalBlockDevice(node=node, size=device_size)
        Filesystem.objects.create(
            node_config=node.current_config,
            block_device=device,
            mount_point="/export/home",
            fstype=FILESYSTEM_TYPE.EXT4,
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("['There is another filesystem on this device.']"),
        ):
            raid.add_device(device, FILESYSTEM_TYPE.RAID)
        self.assertEqual(10, raid.filesystems.count())  # Nothing added.
        self.assertEqual(
            (9 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_remove_device_from_array_invalidates_array_fails(self):
        """Checks it's not possible to remove a device from an RAID in such way
        as to make the RAID invalid (a 1-device RAID-0/1, a 2-device RAID-5
        etc). The goal is to make sure we trigger the RAID internal validation.
        """
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(4)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
            uuid=uuid,
            block_devices=block_devices,
        )
        fsids_before = [fs.id for fs in raid.filesystems.all()]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 6 must have at least 4 raid "
                "devices and any number of spares.']}"
            ),
        ):
            raid.remove_device(block_devices[0])
        self.assertEqual(4, raid.filesystems.count())
        self.assertEqual(
            (2 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )
        # Ensure the filesystems are the exact same before and after.
        self.assertCountEqual(
            fsids_before, [fs.id for fs in raid.filesystems.all()]
        )

    def test_remove_partition_from_array_invalidates_array_fails(self):
        """Checks it's not possible to remove a partition from an RAID in such
        way as to make the RAID invalid (a 1-device RAID-0/1, a 2-device RAID-5
        etc). The goal is to make sure we trigger the RAID internal validation.
        """
        node = factory.make_Node(bios_boot_method="uefi")
        device_size = 10 * 1000**4
        partitions = [
            factory.make_PartitionTable(
                table_type=PARTITION_TABLE_TYPE.GPT,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=device_size
                ),
            ).add_partition()
            for _ in range(4)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
            uuid=uuid,
            partitions=partitions,
        )
        fsids_before = [fs.id for fs in raid.filesystems.all()]
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['RAID level 6 must have at least 4 raid "
                "devices and any number of spares.']}"
            ),
        ):
            raid.remove_partition(partitions[0])
        self.assertEqual(4, raid.filesystems.count())
        self.assertEqual(
            (2 * partitions[0].size) - RAID_SUPERBLOCK_OVERHEAD,
            raid.get_size(),
        )
        # Ensure the filesystems are the exact same before and after.
        self.assertCountEqual(
            fsids_before, [fs.id for fs in raid.filesystems.all()]
        )

    def test_remove_device_from_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices[:-2],
            spare_devices=block_devices[-2:],
        )
        raid.remove_device(block_devices[0])
        self.assertEqual(9, raid.filesystems.count())
        self.assertEqual(
            (6 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )

    def test_remove_partition_from_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        partitions = [
            factory.make_PartitionTable(
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=device_size
                )
            ).add_partition()
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            partitions=partitions[:-2],
            spare_partitions=partitions[-2:],
        )
        raid.remove_partition(partitions[0])
        self.assertEqual(9, raid.filesystems.count())
        self.assertEqual(
            (6 * partitions[0].size) - RAID_SUPERBLOCK_OVERHEAD,
            raid.get_size(),
        )

    def test_remove_invalid_partition_from_array_fails(self):
        node = factory.make_Node(bios_boot_method="uefi")
        device_size = 10 * 1000**4
        partitions = [
            factory.make_PartitionTable(
                table_type=PARTITION_TABLE_TYPE.GPT,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=device_size
                ),
            ).add_partition()
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            partitions=partitions,
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("['Partition does not belong to this array.']"),
        ):
            raid.remove_partition(
                factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=device_size
                    )
                ).add_partition()
            )
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(
            (9 * partitions[0].size) - RAID_SUPERBLOCK_OVERHEAD,
            raid.get_size(),
        )

    def test_remove_device_from_array_fails(self):
        node = factory.make_Node()
        device_size = 10 * 1000**4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = str(uuid4())
        raid = RAID.objects.create_raid(
            name="md0",
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices,
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("['Device does not belong to this array.']"),
        ):
            raid.remove_device(
                factory.make_PhysicalBlockDevice(node=node, size=device_size)
            )
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(
            (9 * device_size) - RAID_SUPERBLOCK_OVERHEAD, raid.get_size()
        )


class TestBcache(MAASServerTestCase):
    def test_objects_is_BcacheManager(self):
        self.assertIsInstance(Bcache.objects, BcacheManager)

    def test_group_type_set_to_BCACHE(self):
        obj = Bcache()
        self.assertEqual(FILESYSTEM_GROUP_TYPE.BCACHE, obj.group_type)

    def test_create_bcache_with_physical_block_devices(self):
        """Checks creation of a Bcache with physical block devices for caching
        and backing roles."""
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_set = factory.make_CacheSet(node=node)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        uuid = str(uuid4())
        bcache = Bcache.objects.create_bcache(
            name="bcache0",
            uuid=uuid,
            cache_set=cache_set,
            backing_device=backing_device,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
        )

        # Verify the filesystems were properly created on the target devices
        self.assertEqual(backing_size, bcache.get_size())
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            backing_device.get_effective_filesystem().fstype,
        )
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(
            bcache, backing_device.get_effective_filesystem().filesystem_group
        )

    def test_create_bcache_with_virtual_block_devices(self):
        """Checks creation of a Bcache with virtual block devices for caching
        and backing roles."""
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_size = 1000**4
        # A caching device that's ridiculously fast to read from, but slow for
        # writing to it.
        cache_device = RAID.objects.create_raid(
            block_devices=[
                factory.make_PhysicalBlockDevice(node=node, size=cache_size)
                for _ in range(10)
            ],
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
        ).virtual_device
        cache_set = factory.make_CacheSet(block_device=cache_device)
        # A ridiculously reliable backing store.
        backing_device = RAID.objects.create_raid(
            block_devices=[
                factory.make_PhysicalBlockDevice(node=node, size=backing_size)
                for _ in range(12)
            ],  # 10 data devices, 2 checksum devices.
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
        ).virtual_device

        bcache = Bcache.objects.create_bcache(
            cache_set=cache_set,
            backing_device=backing_device,
            cache_mode=CACHE_MODE_TYPE.WRITEAROUND,
        )

        # Verify the filesystems were properly created on the target devices
        self.assertEqual(
            (10 * backing_size) - RAID_SUPERBLOCK_OVERHEAD, bcache.get_size()
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_CACHE,
            cache_device.get_effective_filesystem().fstype,
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            backing_device.get_effective_filesystem().fstype,
        )
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(
            bcache, backing_device.get_effective_filesystem().filesystem_group
        )

    def test_create_bcache_with_partitions(self):
        """Checks creation of a Bcache with partitions for caching and backing
        roles."""
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_size = 1000**4
        cache_partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=cache_size
            )
        ).add_partition()
        cache_set = factory.make_CacheSet(partition=cache_partition)
        backing_partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=backing_size
            )
        ).add_partition()
        uuid = str(uuid4())
        bcache = Bcache.objects.create_bcache(
            name="bcache0",
            uuid=uuid,
            cache_set=cache_set,
            backing_partition=backing_partition,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
        )

        # Verify the filesystems were properly created on the target devices
        self.assertEqual(backing_partition.size, bcache.get_size())
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_CACHE,
            cache_partition.get_effective_filesystem().fstype,
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            backing_partition.get_effective_filesystem().fstype,
        )
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(
            bcache,
            backing_partition.get_effective_filesystem().filesystem_group,
        )

    def test_create_bcache_with_block_devices_and_partition(self):
        """Checks creation of a Bcache with a partition for caching and a
        physical block device for backing."""
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_size = 1000**4
        cache_partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=cache_size
            )
        ).add_partition()
        cache_set = factory.make_CacheSet(partition=cache_partition)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        uuid = str(uuid4())
        bcache = Bcache.objects.create_bcache(
            name="bcache0",
            uuid=uuid,
            cache_set=cache_set,
            backing_device=backing_device,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
        )

        # Verify the filesystems were properly created on the target devices
        self.assertEqual(backing_size, bcache.get_size())
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_CACHE,
            cache_partition.get_effective_filesystem().fstype,
        )
        self.assertEqual(
            FILESYSTEM_TYPE.BCACHE_BACKING,
            backing_device.get_effective_filesystem().fstype,
        )
        self.assertEqual(cache_set, bcache.cache_set)
        self.assertEqual(
            bcache, backing_device.get_effective_filesystem().filesystem_group
        )

    def test_delete_bcache(self):
        """Ensures deletion of a bcache also deletes bcache filesystems from
        caching and backing devices."""
        node = factory.make_Node()
        backing_size = 10 * 1000**4
        cache_set = factory.make_CacheSet(node=node)
        backing_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size
        )
        bcache = Bcache.objects.create_bcache(
            cache_set=cache_set,
            backing_device=backing_device,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
        )
        bcache.delete()

        # Verify both filesystems were deleted.
        self.assertIsNone(backing_device.get_effective_filesystem())
        # Verify the cache_set is not deleted.
        self.assertIsNotNone(reload_object(cache_set))
