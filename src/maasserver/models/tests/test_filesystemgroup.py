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
from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
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
            size = random.randint(1000, 10 ** 5)
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
