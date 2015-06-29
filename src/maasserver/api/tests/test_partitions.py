# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for blockdevice API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json

from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object


class TestPartitions(APITestCase):

    def test_create_partition(self):
        """
        Tests creation of a partition on a block device.

        Create partition on block device
        - Offset
        - Size
        POST /api/1.0/nodes/{system_id}/blockdevice/{id}/partitions
        """
        self.become_admin()
        block_size = 1024
        device = factory.make_PhysicalBlockDevice(size=8192 * block_size,
                                                  block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        uri = reverse('partition_table_handler', args=[device.node.system_id,
                                                       device.id])

        # Add a partition to the start of the drive (should start on block 0
        # and be 5 blocks long).
        response = self.client.post(uri, {'op': 'add_partition',
                                          'offset': '800',
                                          'size': '4097'})
        partition = json.loads(response.content)

        partition_from_db = partition_table.partitions.get()
        self.assertEqual(partition['start_offset'],
                         partition_from_db.start_offset)
        self.assertEqual(partition['size'], partition_from_db.size)

        # Add a second partition (which should start on block 6 because we
        # won't ask for an offset
        response = self.client.post(uri, {'op': 'add_partition',
                                          'size': '4096'})
        partition = json.loads(response.content)

        partition_from_db = partition_table.partitions.get(id=partition['id'])
        self.assertEqual(partition['start_offset'],
                         partition_from_db.start_offset)
        self.assertEqual(partition['size'], partition_from_db.size)

    def test_list_partitions(self):
        """Lists all partitions on a given device

        GET /nodes/{system_id}/blockdevice/{id}/partitions
        """
        block_size = 1024
        device = factory.make_PhysicalBlockDevice(size=8192 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition1 = factory.make_Partition(partition_table=partition_table,
                                            start_offset=0, size=4096 *
                                            block_size)
        partition2 = factory.make_Partition(partition_table=partition_table,
                                            start_offset=4096 * block_size,
                                            size=4096 * block_size)
        uri = reverse('partition_table_handler', args=[device.node.system_id,
                                                       device.id])
        response = self.client.get(uri)
        partitions = json.loads(response.content)
        p1 = [p for p in partitions if p['id'] == partition1.id][0]
        p2 = [p for p in partitions if p['id'] == partition2.id][0]

        self.assertEqual(p1['start_offset'], partition1.start_offset)
        self.assertEqual(p1['size'], partition1.size)
        self.assertEqual(p2['start_offset'], partition2.start_offset)
        self.assertEqual(p2['size'], partition2.size)

    def test_read_partition(self):
        """Tests reading metadata about a partition

        Read partition on block device
        GET /api/1.0/nodes/{system_id}/blockdevice/{id}/partitions/{idx}
        """
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(size=8192 * block_size,
                                                  block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(partition_table=partition_table,
                                           start_offset=10 * block_size,
                                           size=4096 * block_size,
                                           bootable=True)
        uri = reverse('partition_handler', args=[device.node.system_id,
                                                 device.id,
                                                 partition.id])
        response = self.client.get(uri)
        parsed_partition = json.loads(response.content)

        self.assertTrue(parsed_partition['bootable'])
        self.assertEqual(parsed_partition['id'], partition.id)
        self.assertEqual(parsed_partition['size'], partition.size)
        self.assertEqual(parsed_partition['start_offset'],
                         partition.start_offset)

    def test_delete_partition(self):
        """Tests deleting a partition

        Delete partition on block device
        DELETE /api/1.0/nodes/{system_id}/blockdevice/{id}/partitions/{idx}
        """
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(size=8192 * block_size,
                                                  block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(partition_table=partition_table,
                                           start_offset=4096 * block_size,
                                           size=4096 * block_size)
        uri = reverse('partition_handler', args=[device.node.system_id,
                                                 device.id,
                                                 partition.id])
        response = self.client.delete(uri)

        # Should return no content and a 204 status_code
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(partition))
