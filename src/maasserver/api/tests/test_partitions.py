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
import random
from uuid import uuid4

from django.core.urlresolvers import reverse
from maasserver.enum import FILESYSTEM_TYPE
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
        self.assertEqual(
            partition_from_db.start_offset, partition['start_offset'])
        self.assertEqual(partition_from_db.size, partition['size'])

        # Add a second partition (which should start on block 6 because we
        # won't ask for an offset
        response = self.client.post(uri, {'op': 'add_partition',
                                          'size': '4096'})
        partition = json.loads(response.content)

        partition_from_db = partition_table.partitions.get(id=partition['id'])
        self.assertEqual(
            partition_from_db.start_offset, partition['start_offset'])
        self.assertEqual(partition_from_db.size, partition['size'])

    def test_list_partitions(self):
        """Lists all partitions on a given device

        GET /nodes/{system_id}/blockdevice/{id}/partitions
        """
        block_size = 1024
        device = factory.make_PhysicalBlockDevice(size=8192 * block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition1 = factory.make_Partition(
            partition_table=partition_table, start_offset=0,
            size=4096 * block_size)
        partition2 = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_table_handler',
            args=[device.node.system_id, device.id])
        response = self.client.get(uri)
        partitions = json.loads(response.content)
        p1 = [p for p in partitions if p['id'] == partition1.id][0]
        p2 = [p for p in partitions if p['id'] == partition2.id][0]

        self.assertEqual(partition1.start_offset, p1['start_offset'])
        self.assertEqual(partition1.size, p1['size'])
        self.assertEqual(partition2.start_offset, p2['start_offset'])
        self.assertEqual(partition2.size, p2['size'])

    def test_read_partition(self):
        """Tests reading metadata about a partition

        Read partition on block device
        GET /api/1.0/nodes/{system_id}/blockdevice/{id}/partitions/{idx}
        """
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=10 * block_size,
            size=4096 * block_size, bootable=True)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.get(uri)
        parsed_partition = json.loads(response.content)

        self.assertTrue(parsed_partition['bootable'])
        self.assertEqual(partition.id, parsed_partition['id'])
        self.assertEqual(partition.size, parsed_partition['size'])
        self.assertEqual(
            partition.start_offset, parsed_partition['start_offset'])

    def test_delete_partition(self):
        """Tests deleting a partition

        Delete partition on block device
        DELETE /api/1.0/nodes/{system_id}/blockdevice/{id}/partitions/{idx}
        """
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.delete(uri)

        # Returns no content and a 204 status_code.
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(partition))

    def test_format_partition_as_admin(self):
        """Tests formatting a partition

        POST /api/1.0/nodes/{system_id}/blockdevice/{id}/partition/{idx}/
             ?op=format
        """
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        fs_uuid = unicode(uuid4())
        response = self.client.post(uri, {
            'op': 'format',
            'uuid': fs_uuid,
            'fstype': FILESYSTEM_TYPE.EXT4,
            'label': 'mylabel',
        })
        # Returns the filesystem.
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        filesystem = json.loads(response.content)['filesystem']
        self.assertEqual(FILESYSTEM_TYPE.EXT4, filesystem['fstype'])
        self.assertEqual('mylabel', filesystem['label'])
        self.assertEqual(fs_uuid, filesystem['uuid'])

    def test_format_partition_as_node_owner(self):
        """Tests formatting a partition as a the owner of the node

        POST /api/1.0/nodes/{system_id}/blockdevice/{id}/partition/{idx}/
             ?op=format
        """
        block_size = 4096
        node = factory.make_Node(owner=self.logged_in_user)
        device = factory.make_PhysicalBlockDevice(
            node=node, size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        fs_uuid = unicode(uuid4())
        response = self.client.post(uri, {
            'op': 'format',
            'uuid': fs_uuid,
            'fstype': FILESYSTEM_TYPE.EXT4,
            'label': 'mylabel',
        })
        # Returns the filesystem.
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        filesystem = json.loads(response.content)['filesystem']
        self.assertEqual(FILESYSTEM_TYPE.EXT4, filesystem['fstype'])
        self.assertEqual('mylabel', filesystem['label'])
        self.assertEqual(fs_uuid, filesystem['uuid'])

    def test_format_partition_as_other_user(self):
        """Tests formatting a partition as a normal user

        POST /api/1.0/nodes/{system_id}/blockdevice/{id}/partition/{idx}/
             ?op=format
        """
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        fs_uuid = unicode(uuid4())
        response = self.client.post(uri, {
            'op': 'format',
            'uuid': fs_uuid,
            'fstype': FILESYSTEM_TYPE.EXT4,
            'label': 'mylabel',
        })
        # Returns the filesystem.
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_format_missing_partition(self):
        """Tests formatting a missing partition - Fails with a 404.

        POST /api/1.0/nodes/{system_id}/blockdevice/{id}/partition/{idx}/
             ?op=format
        """
        block_size = 4096
        node = factory.make_Node(owner=self.logged_in_user)
        device = factory.make_PhysicalBlockDevice(
            node=node, size=8192 * block_size, block_size=block_size)
        factory.make_PartitionTable(block_device=device)
        partition_id = random.randint(1, 1000)  # Most likely a bogus one
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition_id])
        fs_uuid = unicode(uuid4())
        response = self.client.post(uri, {
            'op': 'format',
            'uuid': fs_uuid,
            'fstype': FILESYSTEM_TYPE.EXT4,
            'label': 'mylabel',
        })
        # Fails with a NOT_FOUND status.
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_format_partition_with_invalid_parameters(self):
        """Tests formatting a partition with invalid parameters

        POST /api/1.0/nodes/{system_id}/blockdevice/{id}/partition/{idx}/
             ?op=format
        """
        block_size = 4096
        node = factory.make_Node(owner=self.logged_in_user)
        device = factory.make_PhysicalBlockDevice(
            node=node, size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.post(uri, {
            'op': 'format',
            'uuid': 'NOT A VALID UUID',
            'fstype': 'FAT16',  # We don't support FAT16
            'label': 'mylabel',
        })
        # Fails with a BAD_REQUEST status.
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)

    def test_unformat_partition_as_admin(self):
        """Unformatting a partition as the administrator succeeds and returns
        an OK status."""
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        factory.make_Filesystem(partition=partition)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.post(uri, {'op': 'unformat'})
        # Returns the partition without the filesystem.
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        partition = json.loads(response.content)
        self.assertIsNone(partition.get('filesystem'),
                          'Partition still has a filesystem.')

    def test_unformat_partition_as_node_owner(self):
        """Unformatting a partition on a node the user is allowed to edit
        succeeds and returns an OK status."""
        block_size = 4096
        node = factory.make_Node(owner=self.logged_in_user)
        device = factory.make_PhysicalBlockDevice(
            node=node, size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table,
            start_offset=4096 * block_size,
            size=4096 * block_size)
        factory.make_Filesystem(partition=partition)
        uri = reverse(
            'partition_handler',
            args=[node.system_id, device.id, partition.id])
        response = self.client.post(uri, {'op': 'unformat'})
        # Returns the partition without the filesystem.
        self.assertEqual(httplib.OK, response.status_code, response.content)
        partition = json.loads(response.content)
        self.assertIsNone(
            partition.get('filesystem'), 'Partition still has a filesystem.')

    def test_unformat_partition_as_other_user(self):
        """Unformatting a partition on a node the user is not allowed to edit
        fails with a FORBIDDEN status."""
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        factory.make_Filesystem(partition=partition)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.post(uri, {'op': 'unformat'})
        # Returns nothing and a FORBIDDEN status
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_unformat_missing_filesystem(self):
        """Unformatting a partition that does not contain a filesystem  fails
        with a BAD_REQUEST status."""
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.post(uri, {'op': 'unformat'})
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)

    def test_unformat_missing_partition(self):
        """Unformatting a partition that does not exist fails with a NOT_FOUND
        status."""
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        factory.make_PartitionTable(block_device=device)
        partition_id = random.randint(1, 1000)  # Most likely a bogus one
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition_id])
        response = self.client.post(uri, {'op': 'unformat'})
        # Returns nothing and a NOT_FOUND status.
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_unformat_mounted_partition(self):
        """Unformatting a mounted partition fails with a BAD_REQUEST status."""
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        factory.make_Filesystem(
            partition=partition, mount_point='/mnt/cantdeleteme')
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.post(uri, {'op': 'unformat'})
        # Returns nothing and a BAD_REQUEST status
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)

    def test_unformat_filesystemgroup_partition(self):
        """Unformatting a partition that's part of a filesystem group fails
        with a BAD_REQUEST status."""
        self.become_admin()
        block_size = 4096
        device = factory.make_PhysicalBlockDevice(
            size=8192 * block_size, block_size=block_size)
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table, start_offset=4096 * block_size,
            size=4096 * block_size)
        filesystem_group = factory.make_FilesystemGroup(node=device.node)
        factory.make_Filesystem(
            partition=partition, filesystem_group=filesystem_group)
        uri = reverse(
            'partition_handler',
            args=[device.node.system_id, device.id, partition.id])
        response = self.client.post(uri, {'op': 'unformat'})
        # Returns nothing and a BAD_REQUEST status
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
