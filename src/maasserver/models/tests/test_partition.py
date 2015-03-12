# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Partition`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from uuid import uuid4

from maasserver.enum import PARTITION_TABLE_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPartition(MAASServerTestCase):
    """Tests for the `Partition` model."""

    def test_get_node_returns_partition_table_node(self):
        partition = factory.make_Partition()
        self.assertEquals(
            partition.partition_table.get_node(), partition.get_node())

    def test_get_block_size_returns_partition_table_block_size(self):
        partition = factory.make_Partition()
        self.assertEquals(
            partition.partition_table.get_block_size(),
            partition.get_block_size())

    def test_doesnt_set_uuid_if_partition_table_is_MBR(self):
        table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR)
        partition = factory.make_Partition(partition_table=table)
        self.assertIsNone(partition.uuid)

    def test_set_uuid_if_partition_table_is_GPT(self):
        table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT)
        partition = factory.make_Partition(partition_table=table)
        self.assertIsNotNone(partition.uuid)

    def test_save_doesnt_overwrite_uuid(self):
        uuid = uuid4()
        table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT)
        partition = factory.make_Partition(partition_table=table, uuid=uuid)
        partition.save()
        self.assertEquals('%s' % uuid, partition.uuid)
