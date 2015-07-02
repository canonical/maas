# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `VirtualBlockDevice`."""

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

from django.core.exceptions import ValidationError
from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import human_readable_bytes
from testtools import ExpectedException
from testtools.matchers import MatchesStructure


class TestVirtualBlockDeviceManager(MAASServerTestCase):
    """Tests for the `VirtualBlockDevice` manager."""

    def test_get_available_name_for_returns_next_idx(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        filesystem_group.save()
        prefix = filesystem_group.get_virtual_block_device_prefix()
        virtual_block_device = filesystem_group.virtual_device
        current_idx = int(
            virtual_block_device.name.replace(prefix, ""))
        self.assertEquals(
            "%s%s" % (prefix, current_idx + 1),
            VirtualBlockDevice.objects.get_available_name_for(
                filesystem_group))

    def test_get_available_name_for_ignores_bad_int(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        filesystem_group.save()
        prefix = filesystem_group.get_virtual_block_device_prefix()
        virtual_block_device = filesystem_group.virtual_device
        virtual_block_device.name = "%s%s" % (prefix, factory.make_name("bad"))
        virtual_block_device.save()
        self.assertEquals(
            "%s0" % prefix,
            VirtualBlockDevice.objects.get_available_name_for(
                filesystem_group))

    def test_create_or_update_for_lvm_does_nothing(self):
        # This will create the filesystem group but not a virtual block
        # device since its a volume group.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertItemsEqual(
            [],
            VirtualBlockDevice.objects.filter(
                filesystem_group=filesystem_group))

    def test_create_or_update_for_raid_creates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0)
        prefix = filesystem_group.get_virtual_block_device_prefix()
        next_name = VirtualBlockDevice.objects.get_available_name_for(
            filesystem_group)
        current_idx = int(next_name.replace(prefix, ""))
        proposed_name = "%s%s" % (prefix, current_idx - 1)
        self.assertThat(
            filesystem_group.virtual_device, MatchesStructure.byEquality(
                name=proposed_name, path="/dev/%s" % proposed_name,
                size=filesystem_group.get_size(),
                block_size=(
                    filesystem_group.get_virtual_block_device_block_size())))

    def test_create_or_update_for_bcache_creates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        prefix = filesystem_group.get_virtual_block_device_prefix()
        next_name = VirtualBlockDevice.objects.get_available_name_for(
            filesystem_group)
        current_idx = int(next_name.replace(prefix, ""))
        proposed_name = "%s%s" % (prefix, current_idx - 1)
        self.assertThat(
            filesystem_group.virtual_device, MatchesStructure.byEquality(
                name=proposed_name, path="/dev/%s" % proposed_name,
                size=filesystem_group.get_size(),
                block_size=(
                    filesystem_group.get_virtual_block_device_block_size())))

    def test_create_or_update_for_raid_updates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_0)
        # Update the size of all block devices to change the size of the
        # filesystem group.
        new_size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        for filesystem in filesystem_group.filesystems.all():
            filesystem.block_device.size = new_size
            filesystem.block_device.save()
        # This also tests the post_save signal on `BlockDevice`. Because the
        # filesystem_group.save() does not need to be called here. The
        # post_save performs that operation.
        self.assertEquals(
            new_size, reload_object(filesystem_group.virtual_device).size)

    def test_create_or_update_for_bcache_updates_block_device(self):
        # This will create the filesystem group and a virtual block device.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        # Update the size of the backing device to change the size of the
        # filesystem group.
        new_size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        backing_filesystem = filesystem_group.get_bcache_backing_filesystem()
        backing_filesystem.block_device.size = new_size
        backing_filesystem.block_device.save()
        # This also tests the post_save signal on `BlockDevice`. Because the
        # filesystem_group.save() does not need to be called here. The
        # post_save performs that operation.
        self.assertEquals(
            new_size, reload_object(filesystem_group.virtual_device).size)


class TestVirtualBlockDevice(MAASServerTestCase):
    """Tests for the `VirtualBlockDevice` model."""

    def test_node_is_set_to_same_node_from_filesystem_group(self):
        block_device = factory.make_VirtualBlockDevice()
        self.assertEquals(
            block_device.filesystem_group.get_node(), block_device.node)

    def test_cannot_save_if_node_is_not_same_node_from_filesystem_group(self):
        block_device = factory.make_VirtualBlockDevice()
        block_device.node = factory.make_Node()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Node must be the same node as the "
                    "filesystem_group.']}")):
            block_device.save()

    def test_cannot_save_if_size_larger_than_volume_group(self):
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        factory.make_VirtualBlockDevice(
            filesystem_group=filesystem_group,
            size=filesystem_group.get_size() / 2)
        new_block_device_size = filesystem_group.get_size()
        human_readable_size = human_readable_bytes(new_block_device_size)
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'There is not enough free space (%s) "
                    "on volume group %s.']}" % (
                        human_readable_size,
                        filesystem_group.name,
                    ))):
            factory.make_VirtualBlockDevice(
                filesystem_group=filesystem_group,
                size=new_block_device_size)

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        block_device = factory.make_VirtualBlockDevice(uuid=uuid)
        self.assertEquals('%s' % uuid, block_device.uuid)
