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
import random
import uuid

from django.core.urlresolvers import reverse
from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    NODE_STATUS,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
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

    def test_create_raises_403_if_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_volume_groups_uri(node)
        response = self.client.post(uri, {
            'name': factory.make_name("vg"),
            'block_devices': [block_device.id],
        })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_raises_409_if_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_volume_groups_uri(node)
        response = self.client.post(uri, {
            'name': factory.make_name("vg"),
            'block_devices': [block_device.id],
        })
        self.assertEqual(
            httplib.CONFLICT, response.status_code, response.content)

    def test_create_raises_400_if_form_validation_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uri = get_volume_groups_uri(node)
        response = self.client.post(uri, {})

        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertItemsEqual(['name'], json.loads(response.content).keys())

    def test_create_creates_with_block_devices_and_partitions(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node)
            for _ in range(3)
        ]
        block_device_ids = [
            block_device.id
            for block_device in block_devices
        ]
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_BLOCK_DEVICE_SIZE * 3) + PARTITION_TABLE_EXTRA_SPACE)
        partition_table = factory.make_PartitionTable(
            block_device=block_device)
        partitions = [
            partition_table.add_partition(size=MIN_BLOCK_DEVICE_SIZE)
            for _ in range(2)
        ]
        partition_ids = [
            partition.id
            for partition in partitions
        ]
        name = factory.make_name("vg")
        vguuid = "%s" % uuid.uuid4()
        uri = get_volume_groups_uri(node)
        response = self.client.post(uri, {
            'name': name,
            'uuid': vguuid,
            'block_devices': block_device_ids,
            'partitions': partition_ids,
        })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_volume_group = json.loads(response.content)
        parsed_device_ids = [
            device["id"]
            for device in parsed_volume_group["devices"]
        ]
        self.assertThat(parsed_volume_group, ContainsDict({
            "uuid": Equals(vguuid),
            "name": Equals(name),
        }))
        self.assertItemsEqual(
            block_device_ids + partition_ids, parsed_device_ids)


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

    def test_update_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.put(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_update_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.put(uri)
        self.assertEqual(
            httplib.CONFLICT, response.status_code, response.content)

    def test_update_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node, group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.put(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_update_updates_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        delete_block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, block_device=delete_block_device,
            filesystem_group=volume_group)
        delete_bd_for_partition = factory.make_PhysicalBlockDevice(node=node)
        delete_table = factory.make_PartitionTable(
            block_device=delete_bd_for_partition)
        delete_partition = factory.make_Partition(partition_table=delete_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=delete_partition,
            filesystem_group=volume_group)
        new_name = factory.make_name("vg")
        new_uuid = "%s" % uuid.uuid4()
        new_block_device = factory.make_PhysicalBlockDevice(node=node)
        new_bd_for_partition = factory.make_PhysicalBlockDevice(node=node)
        new_table = factory.make_PartitionTable(
            block_device=new_bd_for_partition)
        new_partition = factory.make_Partition(partition_table=new_table)
        uri = get_volume_group_uri(volume_group)
        response = self.client.put(uri, {
            "name": new_name,
            "uuid": new_uuid,
            "add_block_devices": [new_block_device.id],
            "remove_block_devices": [delete_block_device.id],
            "add_partitions": [new_partition.id],
            "remove_partitions": [delete_partition.id],
            })
        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        volume_group = reload_object(volume_group)
        self.assertEquals(new_name, volume_group.name)
        self.assertEquals(new_uuid, volume_group.uuid)
        self.assertEquals(
            volume_group.id,
            new_block_device.get_effective_filesystem().filesystem_group.id)
        self.assertEquals(
            volume_group.id,
            new_partition.get_effective_filesystem().filesystem_group.id)
        self.assertIsNone(delete_block_device.get_effective_filesystem())
        self.assertIsNone(delete_partition.get_effective_filesystem())

    def test_delete_deletes_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(volume_group))

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.CONFLICT, response.status_code, response.content)

    def test_delete_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node, group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_create_logical_volume_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {"op": "create_logical_volume"})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_logical_volume_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {"op": "create_logical_volume"})
        self.assertEqual(
            httplib.CONFLICT, response.status_code, response.content)

    def test_create_logical_volume_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node, group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.post(uri, {"op": "create_logical_volume"})
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_create_logical_volume_creates_logical_volume(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        name = factory.make_name("lv")
        vguuid = "%s" % uuid.uuid4()
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, volume_group.get_size())
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {
            "op": "create_logical_volume",
            "name": name,
            "uuid": vguuid,
            "size": size,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        logical_volume = json.loads(response.content)
        self.assertThat(logical_volume, ContainsDict({
            "name": Equals("%s-%s" % (volume_group.name, name)),
            "uuid": Equals(vguuid),
            "size": Equals(size),
            }))

    def test_delete_logical_volume_204_when_invalid_id(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        volume_id = random.randint(0, 100)
        response = self.client.post(uri, {
            "op": "delete_logical_volume",
            "id": volume_id,
            })
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)

    def test_delete_logical_volume_400_when_missing_id(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {
            "op": "delete_logical_volume",
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)

    def test_delete_logical_volume_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        logical_volume = factory.make_VirtualBlockDevice(
            filesystem_group=volume_group)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {
            "op": "delete_logical_volume",
            "id": logical_volume.id,
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_logical_volume_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        logical_volume = factory.make_VirtualBlockDevice(
            filesystem_group=volume_group)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {
            "op": "delete_logical_volume",
            "id": logical_volume.id,
            })
        self.assertEqual(
            httplib.CONFLICT, response.status_code, response.content)

    def test_delete_logical_volume_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node, group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=FILESYSTEM_GROUP_TYPE.LVM_VG))
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.post(uri, {"op": "delete_logical_volume"})
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_logical_volume_deletes_logical_volume(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        logical_volume = factory.make_VirtualBlockDevice(
            filesystem_group=volume_group)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {
            "op": "delete_logical_volume",
            "id": logical_volume.id,
            })
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(logical_volume))
