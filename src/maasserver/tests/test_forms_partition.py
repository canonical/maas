# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for all forms that are used with `Partition`."""

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
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_TYPE,
)
from maasserver.forms import (
    AddPartitionForm,
    FormatPartitionForm,
)
from maasserver.models import Filesystem
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block
from maasserver.utils.orm import get_one


class TestAddPartitionForm(MAASServerTestCase):

    def test_requires_fields(self):
        form = AddPartitionForm(
            block_device=factory.make_BlockDevice(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['size'], form.errors.keys())

    def test_is_not_valid_if_size_less_than_min_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'size': MIN_BLOCK_DEVICE_SIZE - 1,
            }
        form = AddPartitionForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because size below zero.")
        self.assertEquals({
            'size': [
                "Ensure this value is greater than or equal to %s." % (
                    MIN_BLOCK_DEVICE_SIZE),
            ]},
            form._errors)

    def test_is_not_valid_if_size_greater_than_block_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'size': block_device.size + 1,
            }
        form = AddPartitionForm(block_device, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because size is to large.")
        self.assertEquals({
            'size': [
                "Ensure this value is less than or equal to %s." % (
                    block_device.size),
            ]},
            form._errors)

    def test_is_valid_if_size_a_string(self):
        block_device = factory.make_PhysicalBlockDevice()
        k_size = (MIN_BLOCK_DEVICE_SIZE / 1000) + 1
        size = "%sk" % k_size
        data = {
            'size': size,
            }
        form = AddPartitionForm(block_device, data=data)
        self.assertTrue(
            form.is_valid(),
            "Should be valid because size is large enough and a string.")

    def test_size_rounded_down_and_placed_on_alignment_boundry(self):
        block_size = 4096
        block_device = factory.make_PhysicalBlockDevice(block_size=block_size)
        k_size = (MIN_BLOCK_DEVICE_SIZE / 1000) + 1
        size = "%sk" % k_size
        rounded_size = round_size_to_nearest_block(
            k_size * 1000, PARTITION_ALIGNMENT_SIZE, False)
        data = {
            'size': size,
            }
        form = AddPartitionForm(block_device, data=data)
        self.assertTrue(form.is_valid())
        partition = form.save()
        self.assertEquals(rounded_size, partition.size)

    def test_uuid_is_set_on_partition(self):
        block_device = factory.make_PhysicalBlockDevice()
        part_uuid = "%s" % uuid.uuid4()
        data = {
            'size': MIN_BLOCK_DEVICE_SIZE,
            'uuid': part_uuid,
            }
        form = AddPartitionForm(block_device, data=data)
        self.assertTrue(form.is_valid())
        partition = form.save()
        self.assertEquals(part_uuid, partition.uuid)

    def test_bootable_is_set_on_partition(self):
        block_device = factory.make_PhysicalBlockDevice()
        data = {
            'size': MIN_BLOCK_DEVICE_SIZE,
            'bootable': True,
            }
        form = AddPartitionForm(block_device, data=data)
        self.assertTrue(form.is_valid())
        partition = form.save()
        self.assertTrue(partition.bootable, "Partition should be bootable.")


class TestFormatPartitionForm(MAASServerTestCase):

    def test_requires_fields(self):
        form = FormatPartitionForm(
            partition=factory.make_Partition(), data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual(['fstype'], form.errors.keys())

    def test_is_not_valid_if_invalid_uuid(self):
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        partition = factory.make_Partition()
        data = {
            'fstype': fstype,
            'uuid': factory.make_string(size=32),
            }
        form = FormatPartitionForm(partition, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid uuid.")
        self.assertEquals({'uuid': ["Enter a valid value."]}, form._errors)

    def test_is_not_valid_if_invalid_format_fstype(self):
        partition = factory.make_Partition()
        data = {
            'fstype': FILESYSTEM_TYPE.LVM_PV,
            }
        form = FormatPartitionForm(partition, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because of an invalid fstype.")
        self.assertEquals({
            'fstype': [
                "Select a valid choice. lvm-pv is not one of the "
                "available choices."
                ],
            }, form._errors)

    def test_creates_filesystem(self):
        fsuuid = "%s" % uuid.uuid4()
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        partition = factory.make_Partition()
        data = {
            'uuid': fsuuid,
            'fstype': fstype,
            }
        form = FormatPartitionForm(partition, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        filesystem = get_one(
            Filesystem.objects.filter(partition=partition))
        self.assertIsNotNone(filesystem)
        self.assertEquals(fstype, filesystem.fstype)
        self.assertEquals(fsuuid, filesystem.uuid)

    def test_deletes_old_filesystem_and_creates_new_one(self):
        fstype = factory.pick_choice(FILESYSTEM_FORMAT_TYPE_CHOICES)
        partition = factory.make_Partition()
        prev_filesystem = factory.make_Filesystem(partition=partition)
        data = {
            'fstype': fstype,
            }
        form = FormatPartitionForm(partition, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEquals(
            1,
            Filesystem.objects.filter(partition=partition).count(),
            "Should only be one filesystem that exists for partition.")
        self.assertIsNone(reload_object(prev_filesystem))
        filesystem = get_one(
            Filesystem.objects.filter(partition=partition))
        self.assertIsNotNone(filesystem)
        self.assertEquals(fstype, filesystem.fstype)
