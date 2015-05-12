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

from maasserver.models import BlockDevice
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import Equals


class TestBlockDeviceManager(MAASServerTestCase):
    """Tests for the `BlockDeviceManager`."""

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


class TestBlockDevice(MAASServerTestCase):
    """Tests for the `BlockDevice` model."""

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
