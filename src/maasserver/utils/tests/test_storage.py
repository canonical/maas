# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for storage utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.enum import (
    FILESYSTEM_TYPE,
    NODE_STATUS,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestGetActiveFilesystem(MAASServerTestCase):

    scenarios = (
        ("BlockDevice", {
            "factory": factory.make_BlockDevice,
            "filesystem_property": "block_device",
            }),
        ("Partition", {
            "factory": factory.make_Partition,
            "filesystem_property": "partition",
            }),
        )

    def test__returns_None_when_no_filesystem(self):
        model = self.factory()
        self.assertIsNone(model.filesystem)

    def test__returns_filesystem_if_node_not_in_acquired_state(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        model = self.factory(node=node)
        filesystem = factory.make_Filesystem(**{
            self.filesystem_property: model,
            })
        self.assertEquals(filesystem, model.filesystem)

    def test__returns_acquired_filesystem(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        model = self.factory(node=node)
        factory.make_Filesystem(**{
            self.filesystem_property: model,
            })
        filesystem = factory.make_Filesystem(**{
            self.filesystem_property: model,
            "acquired": True,
            })
        self.assertEquals(filesystem, model.filesystem)

    def test__returns_non_mountable_filesystem(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        model = self.factory(node=node)
        filesystem = factory.make_Filesystem(**{
            self.filesystem_property: model,
            "fstype": FILESYSTEM_TYPE.BCACHE_BACKING,
            })
        self.assertEquals(filesystem, model.filesystem)

    def test__returns_none_when_allocated_state(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        model = self.factory(node=node)
        factory.make_Filesystem(**{
            self.filesystem_property: model,
            "fstype": FILESYSTEM_TYPE.EXT4,
            })
        self.assertIsNone(model.filesystem)
