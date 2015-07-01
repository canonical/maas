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

import re
from uuid import uuid4

from django.core.exceptions import ValidationError
from maasserver.enum import FILESYSTEM_GROUP_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import human_readable_bytes
from testtools import ExpectedException


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
