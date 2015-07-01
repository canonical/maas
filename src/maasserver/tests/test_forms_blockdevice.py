# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `BlockDevice`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import uuid

from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.forms import (
    FormatBlockDeviceForm,
    MountBlockDeviceForm,
)
from maasserver.models import Filesystem
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one


class TestFormatBlockDeviceForm(MAASServerTestCase):

    def test_requires_fields(self):
        form = FormatBlockDeviceForm(
            block_device=factory.make_BlockDevice(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['fstype'], form.errors.keys())

    def test_is_not_valid_if_block_device_has_partition_table(self):
        fstype = factory.pick_enum(FILESYSTEM_TYPE)
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_PartitionTable(block_device=block_device)
        data = {
            'fstype': fstype,
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because block device has a partition table.")
        self.assertEquals({
            '__all__': [
                "Cannot format block device with a partition table.",
            ]},
            form._errors)

    def test_is_not_valid_if_invalid_uuid(self):
        fstype = factory.pick_enum(FILESYSTEM_TYPE)
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'fstype': fstype,
            'uuid': factory.make_string(size=32),
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid uuid.")
        self.assertEquals({'uuid': ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_invalid_uuid_append_XYZ(self):
        fstype = factory.pick_enum(FILESYSTEM_TYPE)
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'fstype': fstype,
            'uuid': "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaXYZ",
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid uuid.")
        self.assertEquals({'uuid': ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_invalid_uuid_prepend_XYZ(self):
        fstype = factory.pick_enum(FILESYSTEM_TYPE)
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'fstype': fstype,
            'uuid': "XYZaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid uuid.")
        self.assertEquals({'uuid': ["Enter a valid value."]}, form._errors)

    def test_creates_filesystem(self):
        fsuuid = "%s" % uuid.uuid4()
        fstype = factory.pick_enum(FILESYSTEM_TYPE)
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'uuid': fsuuid,
            'fstype': fstype,
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        filesystem = get_one(
            Filesystem.objects.filter(block_device=block_device))
        self.assertIsNotNone(filesystem)
        self.assertEquals(fstype, filesystem.fstype)
        self.assertEquals(fsuuid, filesystem.uuid)

    def test_deletes_old_filesystem_and_creates_new_one(self):
        fstype = factory.pick_enum(FILESYSTEM_TYPE)
        block_device = factory.make_PhysicalBlockDevice()
        prev_filesystem = factory.make_Filesystem(block_device=block_device)
        data = {
            'fstype': fstype,
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEquals(
            1,
            Filesystem.objects.filter(block_device=block_device).count(),
            "Should only be one filesystem that exists for block device.")
        self.assertIsNone(reload_object(prev_filesystem))
        filesystem = get_one(
            Filesystem.objects.filter(block_device=block_device))
        self.assertIsNotNone(filesystem)
        self.assertEquals(fstype, filesystem.fstype)


class TestMountBlockDeviceForm(MAASServerTestCase):

    def test_requires_fields(self):
        form = MountBlockDeviceForm(
            block_device=factory.make_BlockDevice(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['mount_point'], form.errors.keys())

    def test_is_not_valid_if_block_device_has_no_filesystem(self):
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'mount_point': factory.make_absolute_path(),
            }
        form = MountBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because block device does "
            "not have a filesystem.")
        self.assertEquals({
            '__all__': [
                "Cannot mount an unformatted block device.",
            ]},
            form._errors)

    def test_is_not_valid_if_block_device_in_filesystem_group(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.LVM_PV)
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[filesystem])
        data = {
            'mount_point': factory.make_absolute_path(),
            }
        form = MountBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because block device is in a filesystem group.")
        self.assertEquals({
            '__all__': [
                "Filesystem is part of a filesystem group, and cannot be "
                "mounted.",
            ]},
            form._errors)

    def test_is_not_valid_if_invalid_absolute_path(self):
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_Filesystem(block_device=block_device)
        data = {
            'mount_point': factory.make_absolute_path()[1:],
            }
        form = MountBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because its not an absolute path.")
        self.assertEquals(
            {'mount_point': ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_invalid_absolute_path_empty(self):
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_Filesystem(block_device=block_device)
        data = {
            'mount_point': "",
            }
        form = MountBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because its not an absolute path.")
        self.assertEquals(
            {'mount_point': ["This field is required."]}, form._errors)

    def test_is_not_valid_if_invalid_absolute_path_to_long(self):
        block_device = factory.make_PhysicalBlockDevice()
        factory.make_Filesystem(block_device=block_device)
        mount_point = factory.make_absolute_path(directory_length=4096)
        data = {
            'mount_point': mount_point,
            }
        form = MountBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because its not an absolute path.")
        self.assertEquals({
            'mount_point': [
                "Ensure this value has at most 4095 characters "
                "(it has %s)." % len(mount_point)
                ],
            }, form._errors)

    def test_sets_mount_point_on_filesystem(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        mount_point = factory.make_absolute_path()
        data = {
            'mount_point': mount_point,
            }
        form = MountBlockDeviceForm(block_device, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        filesystem = reload_object(filesystem)
        self.assertEquals(mount_point, filesystem.mount_point)
