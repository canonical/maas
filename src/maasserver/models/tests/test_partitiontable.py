# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `PartitionTable`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPartitionTable(MAASServerTestCase):
    """Tests for the `PartitionTable` model."""

    def test_get_node_returns_block_device_node(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.node, partition_table.get_node())

    def test_get_size_returns_block_device_size(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.size, partition_table.get_size())

    def test_get_block_size_returns_block_device_block_size(self):
        partition_table = factory.make_PartitionTable()
        self.assertEquals(
            partition_table.block_device.block_size,
            partition_table.get_block_size())
