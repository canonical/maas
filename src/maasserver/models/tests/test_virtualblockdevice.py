# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
import re
from uuid import uuid4

from django.core.exceptions import ValidationError

from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.filesystemgroup import RAID_SUPERBLOCK_OVERHEAD
from maasserver.models.nodeconfig import NODE_CONFIG_TYPE
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import reload_object


class TestVirtualBlockDeviceManager(MAASServerTestCase):
    """Tests for the `VirtualBlockDevice` manager."""

    def test_create_or_update_for_lvm_does_nothing(self):
        # This will create the filesystem group but not a virtual block
        # device since its a volume group.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        self.assertCountEqual(
            [],
            VirtualBlockDevice.objects.filter(
                filesystem_group=filesystem_group
            ),
        )

    def test_create_or_update_for_raid_creates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0
        )
        device = filesystem_group.virtual_device
        self.assertEqual(device.name, filesystem_group.name)
        self.assertEqual(device.size, filesystem_group.get_size())
        self.assertEqual(
            device.block_size,
            filesystem_group.get_virtual_block_device_block_size(),
        )

    def test_create_or_update_for_bcache_creates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        device = filesystem_group.virtual_device
        self.assertEqual(device.name, filesystem_group.name)
        self.assertEqual(device.size, filesystem_group.get_size())
        self.assertEqual(
            device.block_size,
            filesystem_group.get_virtual_block_device_block_size(),
        )

    def test_create_or_update_for_raid_updates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0
        )
        # Update the size of all block devices to change the size of the
        # filesystem group.
        # The hard-coded size is due to this random ValidationError:
        # {'size': ['Ensure this value is greater than or equal to 4194304.']}
        new_size = random.randint(4194304, 1000 * 1000 * 1000)
        for filesystem in filesystem_group.filesystems.all():
            filesystem.block_device.size = new_size
            filesystem.block_device.save()
        # This also tests the post_save signal on `BlockDevice`. Because the
        # filesystem_group.save() does not need to be called here. The
        # post_save performs that operation.

        # The new size of the RAID-0 array should be the size of the smallest
        # filesystem (in this case, they are all the same) times the number of
        # filesystems in it.
        array_size = (
            new_size - RAID_SUPERBLOCK_OVERHEAD
        ) * filesystem_group.filesystems.count()
        self.assertEqual(
            array_size,
            reload_object(filesystem_group.virtual_device).size,
        )

    def test_create_or_update_for_bcache_updates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        # Update the size of the backing device to change the size of the
        # filesystem group.
        # The hard-coded size is due to this random ValidationError:
        # {'size': ['Ensure this value is greater than or equal to 4194304.']}
        new_size = random.randint(4194304, 1000 * 1000 * 1000)
        backing_filesystem = filesystem_group.get_bcache_backing_filesystem()
        backing_filesystem.block_device.size = new_size
        backing_filesystem.block_device.save()
        # This also tests the post_save signal on `BlockDevice`. Because the
        # filesystem_group.save() does not need to be called here. The
        # post_save performs that operation.
        self.assertEqual(
            new_size, reload_object(filesystem_group.virtual_device).size
        )


class TestVirtualBlockDevice(MAASServerTestCase):
    """Tests for the `VirtualBlockDevice` model."""

    def test_get_name_returns_concat_volume_group_name(self):
        name = factory.make_name("lv")
        vgname = factory.make_name("vg")
        volume_group = factory.make_VolumeGroup(name=vgname)
        logical_volume = factory.make_VirtualBlockDevice(
            name=name, filesystem_group=volume_group
        )
        self.assertEqual(f"{vgname}-{name}", logical_volume.get_name())

    def test_get_name_returns_just_name(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            )
        )
        virtual_device = filesystem_group.virtual_device
        self.assertEqual(virtual_device.name, virtual_device.get_name())

    def test_node_is_set_to_same_node_from_filesystem_group(self):
        block_device = factory.make_VirtualBlockDevice()
        self.assertEqual(
            block_device.filesystem_group.get_node(), block_device.get_node()
        )

    def test_cannot_save_if_node_is_not_same_node_config_from_filesystem_group(
        self,
    ):
        node = factory.make_Node()
        block_device = factory.make_VirtualBlockDevice()
        block_device.node_config = factory.make_NodeConfig(
            node=node, name=NODE_CONFIG_TYPE.DEPLOYMENT
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['Node config must be the same as the "
                "filesystem_group one.']}"
            ),
        ):
            block_device.save()

    def test_cannot_save_if_size_larger_than_volume_group(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        factory.make_VirtualBlockDevice(
            filesystem_group=filesystem_group,
            size=filesystem_group.get_size() / 2,
        )
        new_block_device_size = filesystem_group.get_size()
        human_readable_size = human_readable_bytes(new_block_device_size)
        with self.assertRaisesRegex(
            ValidationError,
            re.escape(
                "{'__all__': ['There is not enough free space (%s) "
                "on volume group %s.']}"
                % (human_readable_size, filesystem_group.name)
            ),
        ):
            factory.make_VirtualBlockDevice(
                filesystem_group=filesystem_group, size=new_block_device_size
            )

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        block_device = factory.make_VirtualBlockDevice(uuid=uuid)
        self.assertEqual(block_device.uuid, str(uuid))

    def test_get_parents_finds_devices(self):
        node = factory.make_Node()
        factory.make_FilesystemGroup(
            node=node,
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            ),
        )
        fs_group_disks = [
            block_device.blockdevice_ptr
            for block_device in node.physicalblockdevice_set.all()
            if not block_device.is_boot_disk()
        ]
        virtualblockdevice = node.virtualblockdevice_set.first()
        self.assertEqual(
            len(fs_group_disks), len(virtualblockdevice.get_parents())
        )

    def test_get_parents_handles_cache_set(self):
        # Regression test for lp1519397
        node = factory.make_Node(with_boot_disk=False)
        volume_group = factory.make_VolumeGroup(node=node)
        name = factory.make_name()
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, volume_group.get_size())
        logical_volume = volume_group.create_logical_volume(
            name=name, uuid=uuid4(), size=size
        )
        logical_volume = reload_object(logical_volume)
        sdb = factory.make_PhysicalBlockDevice(node=node)
        factory.make_CacheSet(block_device=sdb, node=node)
        self.assertCountEqual(
            [fs.block_device_id for fs in volume_group.filesystems.all()],
            [parent.id for parent in logical_volume.get_parents()],
        )
