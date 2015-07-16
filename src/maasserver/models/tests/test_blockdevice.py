# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BlockDevice`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.http import Http404
from maasserver.enum import NODE_PERMISSION
from maasserver.models import (
    BlockDevice,
    FilesystemGroup,
    PhysicalBlockDevice,
    VirtualBlockDevice,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledWith
from mock import MagicMock
from testtools import ExpectedException
from testtools.matchers import Equals


class TestBlockDeviceManagerGetBlockDeviceOr404(MAASServerTestCase):
    """Tests for the `BlockDeviceManager.get_block_device_or_404`."""

    def test__raises_Http404_when_invalid_node(self):
        user = factory.make_admin()
        block_device = factory.make_BlockDevice()
        self.assertRaises(
            Http404, BlockDevice.objects.get_block_device_or_404,
            factory.make_name("system_id"), block_device.id, user,
            NODE_PERMISSION.VIEW)

    def test__raises_Http404_when_invalid_device(self):
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertRaises(
            Http404, BlockDevice.objects.get_block_device_or_404,
            node.system_id, random.randint(0, 100), user,
            NODE_PERMISSION.VIEW)

    def test__view_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.assertRaises(
            PermissionDenied, BlockDevice.objects.get_block_device_or_404,
            node.system_id, device.id, user,
            NODE_PERMISSION.VIEW)

    def test__view_returns_device_when_no_owner(self):
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_PhysicalBlockDevice(node=node)
        self.assertEquals(
            device.id, BlockDevice.objects.get_block_device_or_404(
                node.system_id, device.id, user, NODE_PERMISSION.VIEW).id)

    def test__view_returns_device_when_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_PhysicalBlockDevice(node=node)
        self.assertEquals(
            device.id, BlockDevice.objects.get_block_device_or_404(
                node.system_id, device.id, user, NODE_PERMISSION.VIEW).id)

    def test__edit_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.assertRaises(
            PermissionDenied, BlockDevice.objects.get_block_device_or_404,
            node.system_id, device.id, user,
            NODE_PERMISSION.EDIT)

    def test__edit_returns_device_when_user_is_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_BlockDevice(node=node)
        self.assertEquals(
            device.id, BlockDevice.objects.get_block_device_or_404(
                node.system_id, device.id, user, NODE_PERMISSION.EDIT).id)

    def test__admin_raises_PermissionDenied_when_user_requests_admin(self):
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertRaises(
            PermissionDenied, BlockDevice.objects.get_block_device_or_404,
            node.system_id, device.id, user,
            NODE_PERMISSION.ADMIN)

    def test__admin_returns_device_when_admin(self):
        user = factory.make_admin()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertEquals(
            device.id, BlockDevice.objects.get_block_device_or_404(
                node.system_id, device.id, user, NODE_PERMISSION.ADMIN).id)


class TestBlockDeviceManager(MAASServerTestCase):
    """Tests for the `BlockDeviceManager`."""

    def test__raises_Http404_when_invalid_node(self):
        user = factory.make_admin()
        block_device = factory.make_BlockDevice()
        self.assertRaises(
            Http404, BlockDevice.objects.get_block_device_or_404,
            factory.make_name("system_id"), block_device.id, user,
            NODE_PERMISSION.VIEW)

    def test__raises_Http404_when_invalid_device(self):
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertRaises(
            Http404, BlockDevice.objects.get_block_device_or_404,
            node.system_id, random.randint(0, 100), user,
            NODE_PERMISSION.VIEW)

    def test__returns_device_when_admin(self):
        user = factory.make_admin()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertEquals(
            device.id, BlockDevice.objects.get_block_device_or_404(
                node.system_id, device.id, user, NODE_PERMISSION.ADMIN).id)

    def test__raises_PermissionDenied_when_user_requests_admin(self):
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertRaises(
            PermissionDenied, BlockDevice.objects.get_block_device_or_404,
            node.system_id, device.id, user,
            NODE_PERMISSION.ADMIN)

    def test_filter_by_tags_returns_devices_with_one_tag(self):
        tags = [factory.make_name('tag') for _ in range(3)]
        other_tags = [factory.make_name('tag') for _ in range(3)]
        devices_with_tags = [
            factory.make_BlockDevice(tags=tags)
            for _ in range(3)
            ]
        for _ in range(3):
            factory.make_BlockDevice(tags=other_tags)
        self.assertItemsEqual(
            devices_with_tags,
            BlockDevice.objects.filter_by_tags([tags[0]]))

    def test_filter_by_tags_returns_devices_with_all_tags(self):
        tags = [factory.make_name('tag') for _ in range(3)]
        other_tags = [factory.make_name('tag') for _ in range(3)]
        devices_with_tags = [
            factory.make_BlockDevice(tags=tags)
            for _ in range(3)
            ]
        for _ in range(3):
            factory.make_BlockDevice(tags=other_tags)
        self.assertItemsEqual(
            devices_with_tags,
            BlockDevice.objects.filter_by_tags(tags))

    def test_filter_by_tags_returns_no_devices(self):
        tags = [factory.make_name('tag') for _ in range(3)]
        for _ in range(3):
            factory.make_BlockDevice(tags=tags)
        self.assertItemsEqual(
            [],
            BlockDevice.objects.filter_by_tags([factory.make_name('tag')]))

    def test_filter_by_tags_returns_devices_with_iterable(self):
        tags = [factory.make_name('tag') for _ in range(3)]
        other_tags = [factory.make_name('tag') for _ in range(3)]
        devices_with_tags = [
            factory.make_BlockDevice(tags=tags)
            for _ in range(3)
            ]
        for _ in range(3):
            factory.make_BlockDevice(tags=other_tags)

        def tag_generator():
            for tag in tags:
                yield tag

        self.assertItemsEqual(
            devices_with_tags,
            BlockDevice.objects.filter_by_tags(tag_generator()))

    def test_filter_by_tags_raise_ValueError_when_unicode(self):
        self.assertRaises(
            ValueError, BlockDevice.objects.filter_by_tags, 'test')

    def test_filter_by_tags_raise_ValueError_when_not_iterable(self):
        self.assertRaises(
            ValueError, BlockDevice.objects.filter_by_tags, object())

    def test_get_free_block_devices_for_node(self):
        node = factory.make_Node()
        free_devices = [
            factory.make_BlockDevice(node=node)
            for _ in range(3)
        ]
        # Block devices with partition tables.
        for _ in range(3):
            factory.make_PartitionTable(
                block_device=factory.make_BlockDevice(
                    node=node))
        # Block devices with filesystems.
        for _ in range(3):
            factory.make_Filesystem(
                block_device=factory.make_BlockDevice(
                    node=node))
        self.assertItemsEqual(
            free_devices,
            BlockDevice.objects.get_free_block_devices_for_node(node))


class TestBlockDevice(MAASServerTestCase):
    """Tests for the `BlockDevice` model."""

    def test_path(self):
        block_device = factory.make_PhysicalBlockDevice()
        self.assertEquals(
            "/dev/disk/by-dname/%s" % block_device.name,
            block_device.path)

    def test_type_physical(self):
        block_device = factory.make_PhysicalBlockDevice()
        self.assertEquals("physical", block_device.type)

    def test_type_virtual(self):
        block_device = factory.make_VirtualBlockDevice()
        self.assertEquals("virtual", block_device.type)

    def test_type_raise_ValueError(self):
        block_device = factory.make_BlockDevice()
        with ExpectedException(ValueError):
            block_device.type

    def test_actual_instance_returns_PhysicalBlockDevice(self):
        block_device = factory.make_PhysicalBlockDevice()
        parent_type = BlockDevice.objects.get(id=block_device.id)
        self.assertIsInstance(
            parent_type.actual_instance, PhysicalBlockDevice)

    def test_actual_instance_returns_VirtualBlockDevice(self):
        block_device = factory.make_VirtualBlockDevice()
        parent_type = BlockDevice.objects.get(id=block_device.id)
        self.assertIsInstance(
            parent_type.actual_instance, VirtualBlockDevice)

    def test_actual_instance_returns_BlockDevice(self):
        block_device = factory.make_BlockDevice()
        self.assertIsInstance(
            block_device.actual_instance, BlockDevice)

    def test_filesystem_returns_None_when_no_filesystem(self):
        block_device = factory.make_BlockDevice()
        self.assertIsNone(block_device.filesystem)

    def test_filesystem_returns_filesystem(self):
        block_device = factory.make_BlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        self.assertEquals(filesystem, block_device.filesystem)

    def test_display_size(self):
        sizes = (
            (45, '45.0 bytes'),
            (1000, '1.0 KB'),
            (1000 * 1000, '1.0 MB'),
            (1000 * 1000 * 500, '500.0 MB'),
            (1000 * 1000 * 1000, '1.0 GB'),
            (1000 * 1000 * 1000 * 1000, '1.0 TB'),
            )
        block_device = BlockDevice()
        for (size, display_size) in sizes:
            block_device.size = size
            self.expectThat(
                block_device.display_size(),
                Equals(display_size))

    def test_add_tag_adds_new_tag(self):
        block_device = BlockDevice()
        tag = factory.make_name('tag')
        block_device.add_tag(tag)
        self.assertItemsEqual([tag], block_device.tags)

    def test_add_tag_doesnt_duplicate(self):
        block_device = BlockDevice()
        tag = factory.make_name('tag')
        block_device.add_tag(tag)
        block_device.add_tag(tag)
        self.assertItemsEqual([tag], block_device.tags)

    def test_remove_tag_deletes_tag(self):
        block_device = BlockDevice()
        tag = factory.make_name('tag')
        block_device.add_tag(tag)
        block_device.remove_tag(tag)
        self.assertItemsEqual([], block_device.tags)

    def test_remove_tag_doesnt_error_on_missing_tag(self):
        block_device = BlockDevice()
        tag = factory.make_name('tag')
        #: Test is this doesn't raise an exception
        block_device.remove_tag(tag)

    def test_negative_size(self):
        node = factory.make_Node()
        blockdevice = BlockDevice(node=node, name='sda', path='/dev/sda',
                                  block_size=512, size=-1)
        self.assertRaises(ValidationError, blockdevice.save)

    def test_minimum_size(self):
        node = factory.make_Node()
        blockdevice = BlockDevice(node=node, name='sda', path='/dev/sda',
                                  block_size=512, size=143359)
        self.assertRaises(ValidationError, blockdevice.save)

    def test_negative_block_device_size(self):
        node = factory.make_Node()
        blockdevice = BlockDevice(node=node, name='sda', path='/dev/sda',
                                  block_size=-1, size=143360)
        self.assertRaises(ValidationError, blockdevice.save)

    def test_minimum_block_device_size(self):
        node = factory.make_Node()
        blockdevice = BlockDevice(node=node, name='sda', path='/dev/sda',
                                  block_size=511, size=143360)
        self.assertRaises(ValidationError, blockdevice.save)


class TestBlockDevicePostSave(MAASServerTestCase):
    """Tests for the `BlockDevice` post_save signal."""

    scenarios = [
        ("BlockDevice", {"factory": factory.make_BlockDevice}),
        ("PhysicalBlockDevice", {"factory": factory.make_PhysicalBlockDevice}),
        ("VirtualBlockDevice", {"factory": factory.make_VirtualBlockDevice}),
        ]

    def test__calls_save_on_related_filesystem_groups(self):
        mock_filter_by_block_device = self.patch(
            FilesystemGroup.objects, "filter_by_block_device")
        mock_filesystem_group = MagicMock()
        mock_filter_by_block_device.return_value = [
            mock_filesystem_group,
        ]
        self.factory()
        self.assertThat(mock_filesystem_group.save, MockCalledWith())
