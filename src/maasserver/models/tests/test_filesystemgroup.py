# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `FilesystemGroup`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random
import re
from uuid import uuid4

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.http import Http404
from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_RAID_TYPES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    NODE_PERMISSION,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import (
    Bcache,
    BcacheManager,
    FilesystemGroup,
    RAID,
    RAIDManager,
    VolumeGroup,
    VolumeGroupManager,
)
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.testing.factory import factory
from maasserver.testing.orm import (
    reload_object,
    reload_objects,
)
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import machine_readable_bytes
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    MatchesStructure,
    Not,
)


class TestManagersGetObjectOr404(MAASServerTestCase):
    """Tests for the `get_object_or_404` on the managers."""

    scenarios = (
        ("FilesystemGroup", {
            "model": FilesystemGroup,
            "type": None,
        }),
        ("VolumeGroup", {
            "model": VolumeGroup,
            "type": FILESYSTEM_GROUP_TYPE.LVM_VG,
        }),
        ("RAID", {
            "model": RAID,
            "type": FILESYSTEM_GROUP_TYPE.RAID_0,
        }),
        ("Bcache", {
            "model": Bcache,
            "type": FILESYSTEM_GROUP_TYPE.BCACHE,
        }),
    )

    def test__raises_Http404_when_invalid_node(self):
        user = factory.make_admin()
        filesystem_group = factory.make_FilesystemGroup(group_type=self.type)
        self.assertRaises(
            Http404, self.model.objects.get_object_or_404,
            factory.make_name("system_id"), filesystem_group.id, user,
            NODE_PERMISSION.VIEW)

    def test__raises_Http404_when_invalid_device(self):
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertRaises(
            Http404, self.model.objects.get_object_or_404,
            node.system_id, random.randint(0, 100), user,
            NODE_PERMISSION.VIEW)

    def test__view_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertRaises(
            PermissionDenied,
            self.model.objects.get_object_or_404,
            node.system_id, filesystem_group.id, user,
            NODE_PERMISSION.VIEW)

    def test__view_returns_device_when_no_owner(self):
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertEquals(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user,
                NODE_PERMISSION.VIEW).id)

    def test__view_returns_device_when_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertEquals(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user,
                NODE_PERMISSION.VIEW).id)

    def test__edit_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertRaises(
            PermissionDenied,
            self.model.objects.get_object_or_404,
            node.system_id, filesystem_group.id, user,
            NODE_PERMISSION.EDIT)

    def test__edit_returns_device_when_user_is_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertEquals(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user,
                NODE_PERMISSION.EDIT).id)

    def test__admin_raises_PermissionDenied_when_user_requests_admin(self):
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertRaises(
            PermissionDenied,
            self.model.objects.get_object_or_404,
            node.system_id, filesystem_group.id, user,
            NODE_PERMISSION.ADMIN)

    def test__admin_returns_device_when_admin(self):
        user = factory.make_admin()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(
            node=node, group_type=self.type)
        self.assertEquals(
            filesystem_group.id,
            self.model.objects.get_object_or_404(
                node.system_id, filesystem_group.id, user,
                NODE_PERMISSION.ADMIN).id)


class TestManagersFilterByBlockDevice(MAASServerTestCase):
    """Tests for the managers `filter_by_block_device`."""

    def test__volume_group_on_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem])
        filesystem_groups = (
            VolumeGroup.objects.filter_by_block_device(
                block_device))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__volume_group_on_partition(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition = factory.make_Partition(partition_table=partition_table)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem])
        filesystem_groups = (
            VolumeGroup.objects.filter_by_block_device(
                block_device))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__volume_group_on_two_partitions(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition_one = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=block_device.size / 2)
        partition_two_size = (
            block_device.size - partition_one.size - block_device.block_size)
        partition_two = factory.make_Partition(
            partition_table=partition_table, start_offset=partition_one.size,
            size=partition_two_size)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_one)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            VolumeGroup.objects.filter_by_block_device(
                block_device))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__raid_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_one)
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            RAID.objects.filter_by_block_device(
                block_device_one))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__raid_on_partitions(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition_one = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=block_device.size / 2)
        partition_two_size = (
            block_device.size - partition_one.size - block_device.block_size)
        partition_two = factory.make_Partition(
            partition_table=partition_table, start_offset=partition_one.size,
            size=partition_two_size)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_one)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            RAID.objects.filter_by_block_device(
                block_device))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__bcache_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
            block_device=block_device_one)
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            block_device=block_device_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            Bcache.objects.filter_by_block_device(
                block_device_one))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__bcache_on_partitions(self):
        block_device = factory.make_PhysicalBlockDevice()
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition_one = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=block_device.size / 2)
        partition_two_size = (
            block_device.size - partition_one.size - block_device.block_size)
        partition_two = factory.make_Partition(
            partition_table=partition_table, start_offset=partition_one.size,
            size=partition_two_size)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_CACHE, partition=partition_one)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING, partition=partition_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            Bcache.objects.filter_by_block_device(
                block_device))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)


class TestManagersFilterByNode(MAASServerTestCase):
    """Tests for the managers `filter_by_node`."""

    def test__volume_group_on_block_device(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem])
        filesystem_groups = (
            VolumeGroup.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__volume_group_on_partition(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition = factory.make_Partition(partition_table=partition_table)
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem])
        filesystem_groups = (
            VolumeGroup.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__volume_group_on_two_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition_one = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=block_device.size / 2)
        partition_two_size = (
            block_device.size - partition_one.size - block_device.block_size)
        partition_two = factory.make_Partition(
            partition_table=partition_table, start_offset=partition_one.size,
            size=partition_two_size)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_one)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            VolumeGroup.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__raid_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_one)
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, block_device=block_device_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            RAID.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__raid_on_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition_one = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=block_device.size / 2)
        partition_two_size = (
            block_device.size - partition_one.size - block_device.block_size)
        partition_two = factory.make_Partition(
            partition_table=partition_table, start_offset=partition_one.size,
            size=partition_two_size)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_one)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.RAID, partition=partition_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            RAID.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__bcache_on_block_devices(self):
        node = factory.make_Node()
        block_device_one = factory.make_PhysicalBlockDevice(node=node)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
            block_device=block_device_one)
        block_device_two = factory.make_PhysicalBlockDevice(node=node)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            block_device=block_device_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            Bcache.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)

    def test__bcache_on_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partition_one = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=block_device.size / 2)
        partition_two_size = (
            block_device.size - partition_one.size - block_device.block_size)
        partition_two = factory.make_Partition(
            partition_table=partition_table, start_offset=partition_one.size,
            size=partition_two_size)
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_CACHE, partition=partition_one)
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING, partition=partition_two)
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK,
            filesystems=[filesystem_one, filesystem_two])
        filesystem_groups = (
            Bcache.objects.filter_by_node(node))
        result_filesystem_group_ids = [
            fsgroup.id
            for fsgroup in filesystem_groups
        ]
        self.assertItemsEqual(
            [filesystem_group.id], result_filesystem_group_ids)


class TestFilesystemGroupManager(MAASServerTestCase):
    """Tests for the `FilesystemGroupManager`."""

    def test_get_available_name_for_returns_next_idx(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        filesystem_group.save()
        prefix = filesystem_group.get_name_prefix()
        current_idx = int(
            filesystem_group.name.replace(prefix, ""))
        self.assertEquals(
            "%s%s" % (prefix, current_idx + 1),
            FilesystemGroup.objects.get_available_name_for(
                filesystem_group))

    def test_get_available_name_for_ignores_bad_int(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        filesystem_group.save()
        prefix = filesystem_group.get_name_prefix()
        filesystem_group.name = "%s%s" % (prefix, factory.make_name("bad"))
        filesystem_group.save()
        self.assertEquals(
            "%s0" % prefix,
            FilesystemGroup.objects.get_available_name_for(
                filesystem_group))


class TestVolumeGroupManager(MAASServerTestCase):
    """Tests for the `VolumeGroupManager`."""

    def test_create_volume_group_with_name_and_uuid(self):
        block_device = factory.make_PhysicalBlockDevice()
        name = factory.make_name("vg")
        vguuid = "%s" % uuid4()
        volume_group = VolumeGroup.objects.create_volume_group(
            name, [block_device], [], uuid=vguuid)
        self.assertEquals(name, volume_group.name)
        self.assertEquals(vguuid, volume_group.uuid)

    def test_create_volume_group_with_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        name = factory.make_name("vg")
        volume_group = VolumeGroup.objects.create_volume_group(
            name, block_devices, [])
        block_devices_in_vg = [
            filesystem.block_device.actual_instance
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertItemsEqual(block_devices, block_devices_in_vg)

    def test_create_volume_group_with_partitions(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=MIN_BLOCK_DEVICE_SIZE * 2)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        name = factory.make_name("vg")
        volume_group = VolumeGroup.objects.create_volume_group(
            name, [], partitions)
        partitions_in_vg = [
            filesystem.partition
            for filesystem in volume_group.filesystems.all()
        ]
        self.assertItemsEqual(partitions, partitions_in_vg)

    def test_create_volume_group_with_block_devices_and_partitions(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=MIN_BLOCK_DEVICE_SIZE * 2)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        name = factory.make_name("vg")
        volume_group = VolumeGroup.objects.create_volume_group(
            name, block_devices, partitions)
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
        self.assertItemsEqual(block_devices, block_devices_in_vg)
        self.assertItemsEqual(partitions, partitions_in_vg)


class TestFilesystemGroup(MAASServerTestCase):
    """Tests for the `FilesystemGroup` model."""

    def test_virtual_device_raises_AttributeError_for_lvm(self):
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        with ExpectedException(AttributeError):
            fsgroup.virtual_device

    def test_virtual_device_returns_VirtualBlockDevice_for_group(self):
        fsgroup = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        self.assertEquals(
            VirtualBlockDevice.objects.get(filesystem_group=fsgroup),
            fsgroup.virtual_device)

    def test_get_node_returns_first_filesystem_node(self):
        fsgroup = factory.make_FilesystemGroup()
        self.assertEquals(
            fsgroup.filesystems.first().get_node(), fsgroup.get_node())

    def test_get_node_returns_None_if_no_filesystems(self):
        fsgroup = FilesystemGroup()
        self.assertIsNone(fsgroup.get_node())

    def test_get_size_returns_0_if_lvm_without_filesystems(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertEquals(0, fsgroup.get_size())

    def test_get_size_returns_sum_of_all_filesystem_sizes_for_lvm(self):
        node = factory.make_Node()
        total_size = 0
        filesystems = []
        for _ in range(3):
            size = random.randint(
                MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
            total_size += size
            block_device = factory.make_PhysicalBlockDevice(
                node=node, size=size)
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device))
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=filesystems)
        self.assertEquals(total_size, fsgroup.get_size())

    def test_get_size_returns_0_if_raid_without_filesystems(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.RAID_0)
        self.assertEquals(0, fsgroup.get_size())

    def test_get_size_returns_smallest_disk_size_for_raid_0(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        large_size = random.randint(small_size + 1, small_size + (10 ** 5))
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size)),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=large_size)),
        ]
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0, filesystems=filesystems)
        # Size should be twice the smallest device (the rest of the larger
        # device remains unused.
        self.assertEquals(small_size * 2, fsgroup.get_size())

    def test_get_size_returns_smallest_disk_size_for_raid_1(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        large_size = random.randint(small_size + 1, small_size + (10 ** 5))
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size)),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=large_size)),
        ]
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_1, filesystems=filesystems)
        self.assertEquals(small_size, fsgroup.get_size())

    def test_get_size_returns_correct_disk_size_for_raid_4(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        other_size = random.randint(small_size + 1, small_size + (10 ** 5))
        number_of_raid_devices = random.randint(2, 9)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size)),
        ]
        for _ in range(number_of_raid_devices):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size)))
        # Spares are ignored and not taken into calculation.
        for _ in range(3):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size)))
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_4, filesystems=filesystems)
        self.assertEquals(
            small_size * number_of_raid_devices, fsgroup.get_size())

    def test_get_size_returns_correct_disk_size_for_raid_5(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        other_size = random.randint(small_size + 1, small_size + (10 ** 5))
        number_of_raid_devices = random.randint(2, 9)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size)),
        ]
        for _ in range(number_of_raid_devices):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size)))
        # Spares are ignored and not taken into calculation.
        for _ in range(3):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size)))
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5, filesystems=filesystems)
        self.assertEquals(
            small_size * number_of_raid_devices, fsgroup.get_size())

    def test_get_size_returns_correct_disk_size_for_raid_6(self):
        node = factory.make_Node()
        small_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        other_size = random.randint(small_size + 1, small_size + (10 ** 5))
        number_of_raid_devices = random.randint(3, 9)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=small_size)),
        ]
        for _ in range(number_of_raid_devices):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size)))
        # Spares are ignored and not taken into calculation.
        for _ in range(3):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=other_size)))
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_6, filesystems=filesystems)
        self.assertEquals(
            small_size * (number_of_raid_devices - 1), fsgroup.get_size())

    def test_get_size_returns_0_if_bcache_without_backing(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        self.assertEquals(0, fsgroup.get_size())

    def test_get_size_returns_size_of_backing_device_with_bcache(self):
        node = factory.make_Node()
        backing_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        cache_size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE ** 2)
        backing_block_device = factory.make_PhysicalBlockDevice(
            node=node, size=backing_size)
        cache_block_device = factory.make_PhysicalBlockDevice(
            node=node, size=cache_size)
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                block_device=cache_block_device),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=backing_block_device),
        ]
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            cache_mode=CACHE_MODE_TYPE.WRITEBACK, filesystems=filesystems)
        self.assertEquals(backing_size, fsgroup.get_size())

    def test_is_lvm_returns_true_when_LVM_VG(self):
        fsgroup = FilesystemGroup(group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertTrue(fsgroup.is_lvm())

    def test_is_lvm_returns_false_when_not_LVM_VG(self):
        fsgroup = FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        self.assertFalse(fsgroup.is_lvm())

    def test_is_raid_returns_true_for_all_raid_types(self):
        fsgroup = FilesystemGroup()
        for raid_type in FILESYSTEM_GROUP_RAID_TYPES:
            fsgroup.group_type = raid_type
            self.assertTrue(
                fsgroup.is_raid(),
                "is_raid should return true for %s" % raid_type)

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
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.BCACHE))
        self.assertFalse(fsgroup.is_bcache())

    def test_can_save_new_filesystem_group_without_filesystems(self):
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"))
        fsgroup.save()
        self.expectThat(fsgroup.id, Not(Is(None)))
        self.expectThat(fsgroup.filesystems.count(), Equals(0))

    def test_cannot_save_without_filesystems(self):
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"))
        fsgroup.save()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'At least one filesystem must have "
                    "been added.']}")):
            fsgroup.save()

    def test_cannot_save_without_filesystems_from_different_nodes(self):
        filesystems = [
            factory.make_Filesystem(),
            factory.make_Filesystem(),
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'All added filesystems must belong to "
                    "the same node.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
                filesystems=filesystems)

    def test_cannot_save_volume_group_if_invalid_filesystem(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Volume group can only contain lvm "
                    "physical volumes.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
                filesystems=filesystems)

    def test_can_save_volume_group_if_valid_filesystems(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=filesystems)

    def test_cannot_save_volume_group_if_logical_volumes_larger(self):
        node = factory.make_Node()
        filesystem_one = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=factory.make_PhysicalBlockDevice(node=node))
        filesystem_two = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=factory.make_PhysicalBlockDevice(node=node))
        filesystems = [
            filesystem_one,
            filesystem_two,
        ]
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=filesystems)
        factory.make_VirtualBlockDevice(
            size=volume_group.get_size(), filesystem_group=volume_group)
        filesystem_two.delete()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "[u'Volume group cannot be smaller than its "
                    "logical volumes.']")):
            volume_group.save()

    def test_cannot_save_raid_0_with_less_than_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 0 must have at least 2 raid "
                    "devices and no spares.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
                filesystems=filesystems)

    def test_cannot_save_raid_0_with_spare_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(2)
        ]
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                block_device=factory.make_PhysicalBlockDevice(node=node)))
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 0 must have at least 2 raid "
                    "devices and no spares.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
                filesystems=filesystems)

    def test_can_save_raid_0_with_exactly_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(2)
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=filesystems)

    def test_can_save_raid_0_with_more_then_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(10)
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0,
            filesystems=filesystems)

    def test_cannot_save_raid_1_with_less_than_2_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 1 must have at least 2 raid "
                    "devices and any number of spares.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_1,
                filesystems=filesystems)

    def test_can_save_raid_1_with_spare_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(2)
        ]
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE,
                block_device=factory.make_PhysicalBlockDevice(node=node)))
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_1,
            filesystems=filesystems)

    def test_can_save_raid_1_with_2_or_more_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(2, 10))
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_1,
            filesystems=filesystems)

    def test_cannot_save_raid_4_with_less_than_3_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(1, 2))
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 4 must have atleast 3 raid "
                    "devices and any number of spares.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_4,
                filesystems=filesystems)

    def test_can_save_raid_4_with_3_or_more_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(3, 10))
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node)))
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_4,
            filesystems=filesystems)

    def test_cannot_save_raid_5_with_less_than_3_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(1, 2))
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 5 must have atleast 3 raid "
                    "devices and any number of spares.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_5,
                filesystems=filesystems)

    def test_can_save_raid_5_with_3_or_more_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(3, 10))
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node)))
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5,
            filesystems=filesystems)

    def test_cannot_save_raid_6_with_less_than_4_raid_devices(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(1, 3))
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 6 must have atleast 4 raid "
                    "devices and any number of spares.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.RAID_6,
                filesystems=filesystems)

    def test_can_save_raid_6_with_4_or_more_raid_devices_and_spares(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(4, 10))
        ]
        for _ in range(random.randint(1, 5)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=factory.make_PhysicalBlockDevice(node=node)))
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_6,
            filesystems=filesystems)

    def test_cannot_save_bcache_without_cache(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Bcache must contain one cache and one "
                    "backing device.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=filesystems)

    def test_cannot_save_bcache_without_backing(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Bcache must contain one cache and one "
                    "backing device.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=filesystems)

    def test_can_save_bcache_with_cache_and_backing(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node)),
        ]
        # Test is that this does not raise an exception.
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            filesystems=filesystems)

    def test_cannot_save_bcache_with_multiple_caches(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(2, 10))
        ]
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node)))
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Bcache must contain one cache and one "
                    "backing device.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=filesystems)

    def test_cannot_save_bcache_with_multiple_backings(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(2, 10))
        ]
        filesystems.append(
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                block_device=factory.make_PhysicalBlockDevice(node=node)))
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Bcache must contain one cache and one "
                    "backing device.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=filesystems)

    def test_cannot_save_bcache_with_multiple_caches_and_backings(self):
        node = factory.make_Node()
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                block_device=factory.make_PhysicalBlockDevice(node=node))
            for _ in range(random.randint(2, 10))
        ]
        for _ in range(random.randint(2, 10)):
            filesystems.append(
                factory.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                    block_device=factory.make_PhysicalBlockDevice(node=node)))
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Bcache must contain one cache and one "
                    "backing device.']}")):
            factory.make_FilesystemGroup(
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                filesystems=filesystems)

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        fsgroup = factory.make_FilesystemGroup(uuid=uuid)
        self.assertEquals('%s' % uuid, fsgroup.uuid)

    def test_save_doesnt_allow_changing_group_type(self):
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0)
        fsgroup.save()
        fsgroup.group_type = FILESYSTEM_GROUP_TYPE.RAID_1
        error = self.assertRaises(ValidationError, fsgroup.save)
        self.assertEquals(
            "Cannot change the group_type of a FilesystemGroup.",
            error.message)

    def test_save_calls_create_or_update_for_when_filesystems_linked(self):
        mock_create_or_update_for = self.patch(
            VirtualBlockDevice.objects, "create_or_update_for")
        filesystem_group = factory.make_FilesystemGroup()
        self.assertThat(
            mock_create_or_update_for, MockCalledOnceWith(filesystem_group))

    def test_save_doesnt_call_create_or_update_for_when_no_filesystems(self):
        mock_create_or_update_for = self.patch(
            VirtualBlockDevice.objects, "create_or_update_for")
        filesystem_group = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"))
        filesystem_group.save()
        self.assertThat(
            mock_create_or_update_for, MockNotCalled())

    def test_get_lvm_allocated_size_and_get_lvm_free_space(self):
        """Check get_lvm_allocated_size and get_lvm_free_space methods."""
        backing_volume_size = machine_readable_bytes('10G')
        node = factory.make_Node()
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"))
        fsgroup.save()
        for i in range(5):
            block_device = factory.make_BlockDevice(node=node,
                                                    size=backing_volume_size)
            factory.make_Filesystem(filesystem_group=fsgroup,
                                    fstype=FILESYSTEM_TYPE.LVM_PV,
                                    block_device=block_device)
        # Total space should be 50 GB.
        self.assertEqual(fsgroup.get_size(), 50 * 1000 ** 3)

        # Allocate two VirtualBlockDevice's
        factory.make_VirtualBlockDevice(filesystem_group=fsgroup,
                                        size=35 * 1000 ** 3)
        factory.make_VirtualBlockDevice(filesystem_group=fsgroup,
                                        size=5 * 1000 ** 3)

        self.assertEqual(fsgroup.get_lvm_allocated_size(), 40 * 1000 ** 3)
        self.assertEqual(fsgroup.get_lvm_free_space(), 10 * 1000 ** 3)

    def test_get_virtual_block_device_block_size_returns_backing_for_bc(self):
        # This test is not included in the scenario below
        # `TestFilesystemGroupGetVirtualBlockDeviceBlockSize` because it has
        # different logic that doesn't fit in the scenario.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        filesystem = filesystem_group.get_bcache_backing_filesystem()
        self.assertEquals(
            filesystem.get_block_size(),
            filesystem_group.get_virtual_block_device_block_size())

    def test_get_bcache_cache_filesystem_for_bcache(self):
        node = factory.make_Node()
        backing_filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
            block_device=factory.make_PhysicalBlockDevice(node=node))
        cache_filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
            block_device=factory.make_PhysicalBlockDevice(node=node))
        bcache = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
            filesystems=[cache_filesystem, backing_filesystem])
        self.assertEquals(
            cache_filesystem, bcache.get_bcache_cache_filesystem())

    def test_delete_deletes_filesystems_not_block_devices(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=bd)
            for bd in block_devices
            ]
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=filesystems)
        filesystem_group.delete()
        deleted_filesystems = reload_objects(Filesystem, filesystems)
        kept_block_devices = reload_objects(PhysicalBlockDevice, block_devices)
        self.assertItemsEqual([], deleted_filesystems)
        self.assertItemsEqual(block_devices, kept_block_devices)

    def test_delete_cannot_delete_volume_group_with_logical_volumes(self):
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        factory.make_VirtualBlockDevice(
            size=volume_group.get_size(),
            filesystem_group=volume_group)
        error = self.assertRaises(ValidationError, volume_group.delete)
        self.assertEqual(
            "This volume group has logical volumes; it cannot be deleted.",
            error.message)

    def test_delete_deletes_virtual_block_device(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        virtual_device = filesystem_group.virtual_device
        filesystem_group.delete()
        self.assertIsNone(
            reload_object(virtual_device),
            "VirtualBlockDevice should have been deleted.")


class TestFilesystemGroupGetNamePrefix(MAASServerTestCase):

    scenarios = [
        (FILESYSTEM_GROUP_TYPE.LVM_VG, {
            "group_type": FILESYSTEM_GROUP_TYPE.LVM_VG,
            "prefix": "vg",
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_0, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_0,
            "prefix": "md",
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_1, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_1,
            "prefix": "md",
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_4, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_4,
            "prefix": "md",
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_5, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_5,
            "prefix": "md",
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_6, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_6,
            "prefix": "md",
            }),
        (FILESYSTEM_GROUP_TYPE.BCACHE, {
            "group_type": FILESYSTEM_GROUP_TYPE.BCACHE,
            "prefix": "bcache",
            }),
    ]

    def test__returns_prefix(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=self.group_type)
        self.assertEquals(
            self.prefix, filesystem_group.get_name_prefix())


class TestFilesystemGroupGetVirtualBlockDeviceBlockSize(MAASServerTestCase):

    scenarios = [
        (FILESYSTEM_GROUP_TYPE.LVM_VG, {
            "group_type": FILESYSTEM_GROUP_TYPE.LVM_VG,
            "block_size": 4096,
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_0, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_0,
            "block_size": 512,
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_1, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_1,
            "block_size": 512,
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_4, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_4,
            "block_size": 512,
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_5, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_5,
            "block_size": 512,
            }),
        (FILESYSTEM_GROUP_TYPE.RAID_6, {
            "group_type": FILESYSTEM_GROUP_TYPE.RAID_6,
            "block_size": 512,
            }),
        # For BCACHE see
        # `test_get_virtual_block_device_block_size_returns_backing_for_bc`
        # above.
    ]

    def test__returns_block_size(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=self.group_type)
        self.assertEquals(
            self.block_size,
            filesystem_group.get_virtual_block_device_block_size())


class TestVolumeGroup(MAASServerTestCase):

    def test_objects_is_VolumeGroupManager(self):
        self.assertIsInstance(VolumeGroup.objects, VolumeGroupManager)

    def test_group_type_set_to_LVM_VG(self):
        obj = VolumeGroup()
        self.assertEquals(FILESYSTEM_GROUP_TYPE.LVM_VG, obj.group_type)

    def test_update_block_devices_and_partitions(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        new_block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_block_device = factory.make_PhysicalBlockDevice(
            size=MIN_BLOCK_DEVICE_SIZE * 3, node=node)
        partition_table = factory.make_PartitionTable(
            block_device=partition_block_device)
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        new_partition = partition_table.add_partition(
            size=MIN_BLOCK_DEVICE_SIZE)
        initial_bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=bd)
            for bd in block_devices
        ]
        initial_part_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, partition=part)
            for part in partitions
        ]
        volume_group = factory.make_VolumeGroup(
            filesystems=initial_bd_filesystems + initial_part_filesystems)
        deleted_block_device = block_devices[0]
        updated_block_devices = [new_block_device] + block_devices[1:]
        deleted_partition = partitions[0]
        update_partitions = [new_partition] + partitions[1:]
        volume_group.update_block_devices_and_partitions(
            updated_block_devices, update_partitions)
        self.assertIsNone(deleted_block_device.filesystem)
        self.assertIsNone(deleted_partition.filesystem)
        self.assertEquals(
            volume_group.id,
            new_block_device.filesystem.filesystem_group.id)
        self.assertEquals(
            volume_group.id, new_partition.filesystem.filesystem_group.id)
        for device in block_devices[1:] + partitions[1:]:
            self.assertEquals(
                volume_group.id, device.filesystem.filesystem_group.id)

    def test_create_logical_volume(self):
        volume_group = factory.make_VolumeGroup()
        name = factory.make_name()
        vguuid = "%s" % uuid4()
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, volume_group.get_size())
        logical_volume = volume_group.create_logical_volume(
            name=name, uuid=vguuid, size=size)
        logical_volume = reload_object(logical_volume)
        self.assertThat(logical_volume, MatchesStructure.byEquality(
            name=name,
            uuid=vguuid,
            size=size,
            block_size=volume_group.get_virtual_block_device_block_size(),
            ))


class TestRAID(MAASServerTestCase):

    def test_objects_is_RAIDManager(self):
        self.assertIsInstance(RAID.objects, RAIDManager)

    def test_init_raises_ValueError_if_group_type_not_set_to_raid_type(self):
        self.assertRaises(
            ValueError, RAID, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)

    def test_create_raid(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        for bd in block_devices[5:]:
            factory.make_PartitionTable(block_device=bd)
        partitions = [
            bd.get_partitiontable().add_partition()
            for bd in block_devices[5:]
        ]
        spare_block_device = block_devices[0]
        spare_partition = partitions[0]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
            uuid=uuid,
            block_devices=block_devices[1:5],
            partitions=partitions[1:],
            spare_devices=[spare_block_device],
            spare_partitions=[spare_partition])
        self.assertEqual('md0', raid.name)
        self.assertEqual(6 * device_size, raid.get_size())
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_6, raid.group_type)
        self.assertEqual(uuid, raid.uuid)
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(8, raid.filesystems.filter(
            fstype=FILESYSTEM_TYPE.RAID).count())
        self.assertEqual(2, raid.filesystems.filter(
            fstype=FILESYSTEM_TYPE.RAID_SPARE).count())

    def test_create_raid_0_with_a_spare_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 4)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 0 must have at least 2 raid "
                    "devices and no spares.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_0,
                uuid=uuid,
                block_devices=block_devices[1:],
                partitions=[],
                spare_devices=block_devices[:1],
                spare_partitions=[])

    def test_create_raid_without_devices_fails(self):
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'At least one filesystem must have been "
                    "added.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_0,
                uuid=uuid,
                block_devices=[],
                partitions=[],
                spare_devices=[],
                spare_partitions=[])

    def test_create_raid_0_with_one_element_fails(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 0 must have at least 2 raid "
                    "devices and no spares.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_0,
                uuid=uuid,
                block_devices=[block_device],
                partitions=[],
                spare_devices=[],
                spare_partitions=[])

    def test_create_raid_1_with_spares(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        for bd in block_devices[5:]:
            factory.make_PartitionTable(block_device=bd)
        partitions = [
            bd.get_partitiontable().add_partition()
            for bd in block_devices[5:]
        ]
        spare_block_device = block_devices[0]
        spare_partition = partitions[0]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
            uuid=uuid,
            block_devices=block_devices[1:5],
            partitions=partitions[1:],
            spare_devices=[spare_block_device],
            spare_partitions=[spare_partition])
        self.assertEqual('md0', raid.name)
        self.assertEqual(device_size, raid.get_size())
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_1, raid.group_type)
        self.assertEqual(uuid, raid.uuid)
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(8, raid.filesystems.filter(
            fstype=FILESYSTEM_TYPE.RAID).count())
        self.assertEqual(2, raid.filesystems.filter(
            fstype=FILESYSTEM_TYPE.RAID_SPARE).count())

    def test_create_raid_1_with_one_element_fails(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 1 must have at least 2 raid "
                    "devices and any number of spares.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_1,
                uuid=uuid,
                block_devices=[block_device],
                partitions=[],
                spare_devices=[],
                spare_partitions=[])

    def test_create_raid_5_with_spares(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        for bd in block_devices[5:]:
            factory.make_PartitionTable(block_device=bd)
        partitions = [
            bd.get_partitiontable().add_partition()
            for bd in block_devices[5:]
        ]
        spare_block_device = block_devices[0]
        spare_partition = partitions[0]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices[1:5],
            partitions=partitions[1:],
            spare_devices=[spare_block_device],
            spare_partitions=[spare_partition])
        self.assertEqual('md0', raid.name)
        self.assertEqual(7 * device_size, raid.get_size())
        self.assertEqual(FILESYSTEM_GROUP_TYPE.RAID_5, raid.group_type)
        self.assertEqual(uuid, raid.uuid)
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(8, raid.filesystems.filter(
            fstype=FILESYSTEM_TYPE.RAID).count())
        self.assertEqual(2, raid.filesystems.filter(
            fstype=FILESYSTEM_TYPE.RAID_SPARE).count())

    def test_create_raid_5_with_2_elements_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000 ** 4)
            for _ in range(2)
        ]
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 5 must have atleast 3 raid "
                    "devices and any number of spares.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_5,
                uuid=uuid,
                block_devices=block_devices,
                partitions=[],
                spare_devices=[],
                spare_partitions=[])

    def test_create_raid_6_with_3_elements_fails(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'RAID level 6 must have atleast 4 raid "
                    "devices and any number of spares.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_6,
                uuid=uuid,
                block_devices=block_devices,
                partitions=[],
                spare_devices=[],
                spare_partitions=[])

    def test_create_raid_with_block_device_from_other_node_fails(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        block_devices_1 = [
            factory.make_PhysicalBlockDevice(node=node1)
            for _ in range(5)
        ]
        block_devices_2 = [
            factory.make_PhysicalBlockDevice(node=node2)
            for _ in range(5)
        ]
        uuid = unicode(uuid4())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'All added filesystems must belong to the "
                    "same node.']}")):
            RAID.objects.create_raid(
                name='md0',
                level=FILESYSTEM_GROUP_TYPE.RAID_1,
                uuid=uuid,
                block_devices=block_devices_1 + block_devices_2,
                partitions=[],
                spare_devices=[],
                spare_partitions=[])

    def test_add_device_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        device = factory.make_PhysicalBlockDevice(node=node, size=device_size)
        raid.add_device(device, FILESYSTEM_TYPE.RAID)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(10 * device_size, raid.get_size())

    def test_add_spare_device_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        device = factory.make_PhysicalBlockDevice(node=node, size=device_size)
        raid.add_device(device, FILESYSTEM_TYPE.RAID_SPARE)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(9 * device_size, raid.get_size())

    def test_add_partition_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=device_size)).add_partition()
        raid.add_partition(partition, FILESYSTEM_TYPE.RAID)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(10 * device_size, raid.get_size())

    def test_add_spare_partition_to_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=node, size=device_size)).add_partition()
        raid.add_partition(partition, FILESYSTEM_TYPE.RAID_SPARE)
        self.assertEqual(11, raid.filesystems.count())
        self.assertEqual(9 * device_size, raid.get_size())

    def test_add_device_from_another_node_to_array_fails(self):
        node = factory.make_Node()
        other_node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        device = factory.make_PhysicalBlockDevice(
            node=other_node, size=device_size)
        with ExpectedException(
            ValidationError,
            re.escape(
                "[u'Device needs to be from the same node as the rest of the "
                "array.']")):
            raid.add_device(device, FILESYSTEM_TYPE.RAID)
        self.assertEqual(10, raid.filesystems.count())  # Still 10 devices
        self.assertEqual(9 * device_size, raid.get_size())

    def test_add_partition_from_another_node_to_array_fails(self):
        node = factory.make_Node()
        other_node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(
                node=other_node, size=device_size)).add_partition()
        with ExpectedException(
                ValidationError,
            re.escape(
                "[u'Partition must be on a device from the same node as the "
                "rest of the array.']")):
            raid.add_partition(partition, FILESYSTEM_TYPE.RAID)
        self.assertEqual(10, raid.filesystems.count())  # Nothing added
        self.assertEqual(9 * device_size, raid.get_size())

    def test_add_already_used_device_to_array_fails(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        device = factory.make_PhysicalBlockDevice(node=node, size=device_size)
        Filesystem.objects.create(
            block_device=device, mount_point='/export/home',
            fstype=FILESYSTEM_TYPE.EXT4)
        with ExpectedException(
            ValidationError,
            re.escape(
                "[u'There is another filesystem on this device.']")):
            raid.add_device(device, FILESYSTEM_TYPE.RAID)
        self.assertEqual(10, raid.filesystems.count())  # Nothing added.
        self.assertEqual(9 * device_size, raid.get_size())

    def test_remove_device_from_array_invalidates_array_fails(self):
        """Checks it's not possible to remove a device from an RAID in such way
        as to make the RAID invalid (a 1-device RAID-0/1, a 2-device RAID-5
        etc). The goal is to make sure we trigger the RAID internal validation.
        """
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(4)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
            uuid=uuid,
            block_devices=block_devices)
        fsids_before = [fs.id for fs in raid.filesystems.all()]
        with ExpectedException(
            ValidationError,
            re.escape(
                "{'__all__': [u'RAID level 6 must have atleast 4 raid "
                "devices and any number of spares.']}")):
            raid.remove_device(block_devices[0])
        self.assertEqual(4, raid.filesystems.count())
        self.assertEqual(2 * device_size, raid.get_size())
        # Ensure the filesystems are the exact same before and after.
        self.assertItemsEqual(
            fsids_before, [fs.id for fs in raid.filesystems.all()])

    def test_remove_partition_from_array_invalidates_array_fails(self):
        """Checks it's not possible to remove a partition from an RAID in such
        way as to make the RAID invalid (a 1-device RAID-0/1, a 2-device RAID-5
        etc). The goal is to make sure we trigger the RAID internal validation.
        """
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        partitions = [
            factory.make_PartitionTable(
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=device_size)).add_partition()
            for _ in range(4)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_6,
            uuid=uuid,
            partitions=partitions)
        fsids_before = [fs.id for fs in raid.filesystems.all()]
        with ExpectedException(
            ValidationError,
            re.escape(
                "{'__all__': [u'RAID level 6 must have atleast 4 raid "
                "devices and any number of spares.']}")):
            raid.remove_partition(partitions[0])
        self.assertEqual(4, raid.filesystems.count())
        self.assertEqual(2 * device_size, raid.get_size())
        # Ensure the filesystems are the exact same before and after.
        self.assertItemsEqual(
            fsids_before, [fs.id for fs in raid.filesystems.all()])

    def test_remove_device_from_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices[:-2],
            spare_devices=block_devices[-2:])
        raid.remove_device(block_devices[0])
        self.assertEqual(9, raid.filesystems.count())
        self.assertEqual(6 * device_size, raid.get_size())

    def test_remove_partition_from_array(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        partitions = [
            factory.make_PartitionTable(
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=device_size)).add_partition()
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            partitions=partitions[:-2],
            spare_partitions=partitions[-2:])
        raid.remove_partition(partitions[0])
        self.assertEqual(9, raid.filesystems.count())
        self.assertEqual(6 * device_size, raid.get_size())

    def test_remove_invalid_partition_from_array_fails(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        partitions = [
            factory.make_PartitionTable(
                block_device=factory.make_PhysicalBlockDevice(
                    node=node, size=device_size)).add_partition()
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            partitions=partitions)
        with ExpectedException(
            ValidationError,
            re.escape(
                "[u'Partition does not belong to this array.']")):
            raid.remove_partition(
                factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(
                        node=node, size=device_size)).add_partition())
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(9 * device_size, raid.get_size())

    def test_remove_device_from_array_fails(self):
        node = factory.make_Node()
        device_size = 10 * 1000 ** 4
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=device_size)
            for _ in range(10)
        ]
        uuid = unicode(uuid4())
        raid = RAID.objects.create_raid(
            name='md0',
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            uuid=uuid,
            block_devices=block_devices)
        with ExpectedException(
                ValidationError,
                re.escape("[u'Device does not belong to this array.']")):
            raid.remove_device(
                factory.make_PhysicalBlockDevice(node=node, size=device_size))
        self.assertEqual(10, raid.filesystems.count())
        self.assertEqual(9 * device_size, raid.get_size())


class TestBcache(MAASServerTestCase):

    def test_objects_is_BcacheManager(self):
        self.assertIsInstance(Bcache.objects, BcacheManager)

    def test_group_type_set_to_BCACHE(self):
        obj = Bcache()
        self.assertEquals(FILESYSTEM_GROUP_TYPE.BCACHE, obj.group_type)
