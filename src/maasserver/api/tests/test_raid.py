# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for raid API."""

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
from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.utils.converters import human_readable_bytes
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_raid_devices_uri(node):
    """Return a Node's RAID devices URI on the API."""
    return reverse(
        'raid_devices_handler', args=[node.system_id])


def get_raid_device_uri(raid, node=None):
    """Return a RAID device URI on the API."""
    if node is None:
        node = raid.get_node()
    return reverse(
        'raid_device_handler', args=[node.system_id, raid.id])


class TestRAIDDevicesAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            '/api/1.0/nodes/%s/raids/' % (node.system_id),
            get_raid_devices_uri(node))

    def test_read(self):
        node = factory.make_Node()
        raids = [
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_0),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_1),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_4),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_5),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6),
        ]
        # Not RAID. Should not be in the output.
        for _ in range(3):
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        uri = get_raid_devices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            raid.id
            for raid in raids
            ]
        result_ids = [
            raid["id"]
            for raid in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)


class TestRAIDDeviceAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_0)
        self.assertEqual(
            '/api/1.0/nodes/%s/raid/%s/' % (
                node.system_id, raid.id),
            get_raid_device_uri(raid, node=node))

    def test_read(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        block_device_ids = [
            bd.id
            for bd in block_devices
        ]
        bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID, block_device=bd)
            for bd in block_devices
        ]
        spare_block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        spare_block_device_ids = [
            bd.id
            for bd in spare_block_devices
        ]
        spare_bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE, block_device=bd)
            for bd in spare_block_devices
        ]
        partitions = [
            factory.make_Partition(
                partition_table=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)))
            for _ in range(3)
        ]
        partitions_ids = [
            partition.id
            for partition in partitions
        ]
        partition_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID, partition=partition)
            for partition in partitions
        ]
        spare_partitions = [
            factory.make_Partition(
                partition_table=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)))
            for _ in range(3)
        ]
        spare_partitions_ids = [
            partition.id
            for partition in spare_partitions
        ]
        spare_partition_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE, partition=partition)
            for partition in spare_partitions
        ]
        raid = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5,
            filesystems=(
                bd_filesystems + spare_bd_filesystems +
                partition_filesystems + spare_partition_filesystems))
        uri = get_raid_device_uri(raid)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_raid = json.loads(response.content)
        parsed_device_ids = [
            device["id"]
            for device in parsed_raid["devices"]
        ]
        parsed_spare_device_ids = [
            device["id"]
            for device in parsed_raid["spare_devices"]
        ]
        self.assertThat(parsed_raid, ContainsDict({
            "id": Equals(raid.id),
            "uuid": Equals(raid.uuid),
            "name": Equals(raid.name),
            "level": Equals(raid.group_type),
            "size": Equals(raid.get_size()),
            "human_size": Equals(
                human_readable_bytes(raid.get_size())),
            "resource_uri": Equals(get_raid_device_uri(raid)),
            }))
        self.assertItemsEqual(
            block_device_ids + partitions_ids, parsed_device_ids)
        self.assertItemsEqual(
            spare_block_device_ids + spare_partitions_ids,
            parsed_spare_device_ids)
        self.assertEquals(
            raid.virtual_device.id, parsed_raid["virtual_device"]["id"])

    def test_read_404_when_not_raid(self):
        not_raid = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        uri = get_raid_device_uri(not_raid)
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_deletes_raid(self):
        node = factory.make_Node(owner=self.logged_in_user)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_5)
        uri = get_raid_device_uri(raid)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(raid))

    def test_delete_403_when_not_owner(self):
        raid = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_6)
        uri = get_raid_device_uri(raid)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_404_when_not_raid(self):
        node = factory.make_Node(owner=self.logged_in_user)
        not_raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE)
        uri = get_raid_device_uri(not_raid)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)
