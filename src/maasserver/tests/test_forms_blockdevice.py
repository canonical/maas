# Copyright 2015 Canonical Ltd.  This software is licensed under the
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

import random
import uuid

from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.forms import (
    CreatePhysicalBlockDeviceForm,
    FormatBlockDeviceForm,
    MountBlockDeviceForm,
    UpdatePhysicalBlockDeviceForm,
    UpdateVirtualBlockDeviceForm,
)
from maasserver.models import Filesystem
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from testtools.matchers import MatchesStructure


class TestFormatBlockDeviceForm(MAASServerTestCase):

    def test_requires_fields(self):
        form = FormatBlockDeviceForm(
            block_device=factory.make_BlockDevice(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['fstype'], form.errors.keys())

    def test_is_not_valid_if_block_device_has_partition_table(self):
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
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

    def test_is_not_valid_if_invalid_format_fstype(self):
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'fstype': FILESYSTEM_TYPE.LVM_PV,
            }
        form = FormatBlockDeviceForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid fstype.")
        self.assertEquals({
            'fstype': [
                "Select a valid choice. lvm-pv is not one of the "
                "available choices."
                ],
            }, form._errors)

    def test_is_not_valid_if_invalid_uuid(self):
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
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
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
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
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
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
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
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
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
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


class TestCreatePhysicalBlockDeviceForm(MAASServerTestCase):

    def test_requires_fields(self):
        node = factory.make_Node()
        form = CreatePhysicalBlockDeviceForm(node, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            'name': ['This field is required.'],
            'size': ['This field is required.'],
            'block_size': ['This field is required.'],
            '__all__': [
                'serial/model are required if id_path is not provided.'],
            }, form.errors)

    def test_creates_physical_block_device_with_model_serial(self):
        node = factory.make_Node()
        name = factory.make_name("sd")
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10)
        block_size = 4096
        form = CreatePhysicalBlockDeviceForm(node, data={
            'name': name,
            'model': model,
            'serial': serial,
            'size': size,
            'block_size': block_size,
            })
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertThat(block_device, MatchesStructure.byEquality(
            name=name,
            model=model,
            serial=serial,
            size=size,
            block_size=block_size,
            ))

    def test_creates_physical_block_device_with_id_path(self):
        node = factory.make_Node()
        name = factory.make_name("sd")
        id_path = factory.make_absolute_path()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10)
        block_size = 4096
        form = CreatePhysicalBlockDeviceForm(node, data={
            'name': name,
            'id_path': id_path,
            'size': size,
            'block_size': block_size,
            })
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertThat(block_device, MatchesStructure.byEquality(
            name=name,
            id_path=id_path,
            size=size,
            block_size=block_size,
            ))


class TestUpdatePhysicalBlockDeviceForm(MAASServerTestCase):

    def test_requires_no_fields(self):
        block_device = factory.make_PhysicalBlockDevice()
        form = UpdatePhysicalBlockDeviceForm(instance=block_device, data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertItemsEqual([], form.errors.keys())

    def test_updates_physical_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        name = factory.make_name("sd")
        model = factory.make_name("model")
        serial = factory.make_name("serial")
        id_path = factory.make_absolute_path()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 10)
        block_size = 4096
        form = UpdatePhysicalBlockDeviceForm(instance=block_device, data={
            'name': name,
            'model': model,
            'serial': serial,
            'id_path': id_path,
            'size': size,
            'block_size': block_size,
            })
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertThat(block_device, MatchesStructure.byEquality(
            name=name,
            model=model,
            serial=serial,
            id_path=id_path,
            size=size,
            block_size=block_size,
            ))


class TestUpdateVirtualBlockDeviceForm(MAASServerTestCase):

    def test_requires_no_fields(self):
        block_device = factory.make_VirtualBlockDevice()
        form = UpdateVirtualBlockDeviceForm(instance=block_device, data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertItemsEqual([], form.errors.keys())

    def test_updates_virtual_block_device(self):
        block_device = factory.make_VirtualBlockDevice()
        name = factory.make_name("lv")
        vguuid = "%s" % uuid.uuid4()
        size = random.randint(
            MIN_BLOCK_DEVICE_SIZE, block_device.filesystem_group.get_size())
        form = UpdateVirtualBlockDeviceForm(instance=block_device, data={
            'name': name,
            'uuid': vguuid,
            'size': size,
            })
        self.assertTrue(form.is_valid(), form.errors)
        block_device = form.save()
        self.assertThat(block_device, MatchesStructure.byEquality(
            name=name,
            uuid=vguuid,
            size=size,
            ))
