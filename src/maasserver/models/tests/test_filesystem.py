# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Filesystem`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import re
from uuid import uuid4

from django.core.exceptions import ValidationError
from maasserver.models.filesystem import Filesystem
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException


class TestFilesystemManager(MAASServerTestCase):
    """Tests for the `FilesystemManager`."""

    def test_filter_by_node(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        bd_for_partitions = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=bd_for_partitions)
        partition = factory.make_Partition(partition_table=partition_table)
        filesystem_on_bd = factory.make_Filesystem(block_device=block_device)
        filesystem_on_partition = factory.make_Filesystem(partition=partition)
        self.assertItemsEqual(
            [filesystem_on_bd, filesystem_on_partition],
            Filesystem.objects.filter_by_node(node))


class TestFilesystem(MAASServerTestCase):
    """Tests for the `Filesystem` model."""

    def test_get_node_returns_partition_node(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEquals(
            fs.partition.get_node(), fs.get_node())

    def test_get_node_returns_block_device_node(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEquals(
            fs.block_device.node, fs.get_node())

    def test_get_node_returns_None_when_partition_and_block_device_None(self):
        fs = Filesystem()
        self.assertIsNone(fs.get_node())

    def test_get_size_returns_partition_size(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEquals(
            fs.partition.size, fs.get_size())

    def test_get_size_returns_block_device_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEquals(
            fs.block_device.size, fs.get_size())

    def test_get_size_returns_0_when_partition_and_block_device_None(self):
        fs = Filesystem()
        self.assertEquals(0, fs.get_size())

    def test_get_block_size_returns_partition_block_size(self):
        partition = factory.make_Partition()
        fs = factory.make_Filesystem(partition=partition)
        self.assertEquals(
            fs.partition.get_block_size(), fs.get_block_size())

    def test_get_block_size_returns_block_device_block_size(self):
        block_device = factory.make_PhysicalBlockDevice()
        fs = factory.make_Filesystem(block_device=block_device)
        self.assertEquals(
            fs.block_device.block_size, fs.get_block_size())

    def test_get_block_size_returns_0_when_partition_and_device_None(self):
        fs = Filesystem()
        self.assertEquals(0, fs.get_block_size())

    def test_cannot_save_if_boot_partition_and_block_device_missing(self):
        fs = Filesystem()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'One of partition or block_device "
                    "must be specified.']}")):
            fs.save()

    def test_cannot_save_if_both_boot_partition_and_block_device_exists(self):
        fs = Filesystem()
        fs.block_device = factory.make_PhysicalBlockDevice()
        fs.partition = factory.make_Partition()
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'Only one of partition or block_device "
                    "can be specified.']}")):
            fs.save()

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        fs = factory.make_Filesystem(uuid=uuid)
        self.assertEquals('%s' % uuid, fs.uuid)

    def test_get_parent_returns_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        self.assertEquals(block_device, filesystem.get_parent())

    def test_get_parent_returns_partition(self):
        partition = factory.make_Partition()
        filesystem = factory.make_Filesystem(partition=partition)
        self.assertEquals(partition, filesystem.get_parent())
