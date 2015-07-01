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

from django.core.exceptions import ValidationError
from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import machine_readable_bytes
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    Not,
)


class TestFilesystemGroup(MAASServerTestCase):
    """Tests for the `FilesystemGroup` model."""

    def test_get_node_returns_first_filesystem_node(self):
        fsgroup = factory.make_FilesystemGroup()
        self.assertEquals(
            fsgroup.filesystems.first().get_node(), fsgroup.get_node())

    def test_get_node_returns_None_if_no_filesystems(self):
        fsgroup = FilesystemGroup()
        self.assertIsNone(fsgroup.get_node())

    def test_get_size_returns_sum_of_all_filesystem_sizes(self):
        node = factory.make_Node()
        total_size = 0
        filesystems = []
        for _ in range(3):
            size = random.randint(143360, 10 ** 6)
            total_size += size
            block_device = factory.make_PhysicalBlockDevice(
                node=node, size=size)
            filesystems.append(
                factory.make_Filesystem(block_device=block_device))
        fsgroup = factory.make_FilesystemGroup(filesystems=filesystems)
        self.assertEquals(total_size, fsgroup.get_size())

    def test_get_size_returns_0_if_no_filesystems(self):
        fsgroup = FilesystemGroup()
        self.assertEquals(0, fsgroup.get_size())

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
        fsgroup = FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            name=factory.make_name("vg"))
        fsgroup.save()
        fsgroup.filesystems.add(factory.make_Filesystem())
        fsgroup.filesystems.add(factory.make_Filesystem())
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': [u'All added filesystems must belong to "
                    "the same node.']}")):
            fsgroup.save()

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        fsgroup = factory.make_FilesystemGroup(uuid=uuid)
        self.assertEquals('%s' % uuid, fsgroup.uuid)

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
