# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for volume-group API."""

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


def get_volume_groups_uri(node):
    """Return a Node's volume group URI on the API."""
    return reverse(
        'volume_groups_handler', args=[node.system_id])


def get_volume_group_uri(volume_group, node=None):
    """Return a volume group URI on the API."""
    if node is None:
        node = volume_group.get_node()
    return reverse(
        'volume_group_handler', args=[node.system_id, volume_group.id])


class TestVolumeGroups(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            '/api/1.0/nodes/%s/volume-groups/' % (node.system_id),
            get_volume_groups_uri(node))

    def test_read(self):
        node = factory.make_Node()
        volume_groups = [
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
            for _ in range(3)
            ]
        # Not volume groups. Should not be in the output.
        for _ in range(3):
            factory.make_FilesystemGroup(
                node=node, group_type=factory.pick_enum(
                    FILESYSTEM_GROUP_TYPE,
                    but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_groups_uri(node)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            vg.id
            for vg in volume_groups
            ]
        result_ids = [
            vg["id"]
            for vg in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)


class TestVolumeGroupAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        volume_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        self.assertEqual(
            '/api/1.0/nodes/%s/volume-group/%s/' % (
                node.system_id, volume_group.id),
            get_volume_group_uri(volume_group, node=node))

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
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=bd)
            for bd in block_devices
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
                fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition)
            for partition in partitions
        ]
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=bd_filesystems + partition_filesystems)
        logical_volume_ids = [
            factory.make_VirtualBlockDevice(
                filesystem_group=volume_group, size=bd.size).id
            for bd in block_devices
        ]
        uri = get_volume_group_uri(volume_group)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_volume_group = json.loads(response.content)
        parsed_device_ids = [
            device["id"]
            for device in parsed_volume_group["devices"]
        ]
        parsed_logical_volume_ids = [
            lv["id"]
            for lv in parsed_volume_group["logical_volumes"]
        ]
        self.assertThat(parsed_volume_group, ContainsDict({
            "id": Equals(volume_group.id),
            "uuid": Equals(volume_group.uuid),
            "name": Equals(volume_group.name),
            "size": Equals(volume_group.get_size()),
            "human_size": Equals(
                human_readable_bytes(volume_group.get_size())),
            "available_size": Equals(volume_group.get_lvm_free_space()),
            "human_available_size": Equals(
                human_readable_bytes(volume_group.get_lvm_free_space())),
            "used_size": Equals(volume_group.get_lvm_allocated_size()),
            "human_used_size": Equals(
                human_readable_bytes(volume_group.get_lvm_allocated_size())),
            "resource_uri": Equals(get_volume_group_uri(volume_group)),
            }))
        self.assertItemsEqual(
            block_device_ids + partitions_ids, parsed_device_ids)
        self.assertItemsEqual(logical_volume_ids, parsed_logical_volume_ids)

    def test_read_404_when_not_volume_group(self):
        not_volume_group = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_deletes_volume_group(self):
        node = factory.make_Node(owner=self.logged_in_user)
        volume_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(volume_group))

    def test_delete_403_when_not_owner(self):
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_404_when_not_volume_group(self):
        node = factory.make_Node(owner=self.logged_in_user)
        not_volume_group = factory.make_FilesystemGroup(
            node=node, group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)
