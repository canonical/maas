# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for volume-group API."""


import http.client
import json
import random
import uuid

from django.conf import settings
from django.urls import reverse

from maasserver.enum import FILESYSTEM_GROUP_TYPE, FILESYSTEM_TYPE, NODE_STATUS
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.partition import (
    MIN_PARTITION_SIZE,
    PARTITION_ALIGNMENT_SIZE,
)
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import (
    human_readable_bytes,
    round_size_to_nearest_block,
)
from maasserver.utils.orm import reload_object


def get_volume_groups_uri(node):
    """Return a Node's volume group URI on the API."""
    return reverse("volume_groups_handler", args=[node.system_id])


def get_volume_group_uri(volume_group, node=None, test_plural=True):
    """Return a volume group URI on the API."""
    if node is None:
        node = volume_group.get_node()
    ret = reverse(
        "volume_group_handler", args=[node.system_id, volume_group.id]
    )
    # Regression test for LP:1715230 - Both volume-group and volume-groups
    # API endpoints should work
    if test_plural and random.choice([True, False]):
        ret = ret.replace("volume-group", "volume-groups")
    return ret


class TestVolumeGroups(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/volume-groups/" % (node.system_id),
            get_volume_groups_uri(node),
        )

    def test_read(self):
        node = factory.make_Node()
        volume_groups = [
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
            )
            for _ in range(3)
        ]
        # Not volume groups. Should not be in the output.
        for _ in range(3):
            factory.make_FilesystemGroup(
                node=node,
                group_type=factory.pick_enum(
                    FILESYSTEM_GROUP_TYPE,
                    but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG],
                ),
            )
        uri = get_volume_groups_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [vg.id for vg in volume_groups]
        result_ids = [
            vg["id"]
            for vg in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create_raises_403_if_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_volume_groups_uri(node)
        response = self.client.post(
            uri,
            {
                "name": factory.make_name("vg"),
                "block_devices": [block_device.id],
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_raises_409_if_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_volume_groups_uri(node)
        response = self.client.post(
            uri,
            {
                "name": factory.make_name("vg"),
                "block_devices": [block_device.id],
            },
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_create_raises_400_if_form_validation_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uri = get_volume_groups_uri(node)
        response = self.client.post(uri, {})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {"name"},
            json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            ).keys(),
        )

    def test_create_creates_with_block_devices_and_partitions(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_ids = [block_device.id for block_device in block_devices]
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            size=MIN_PARTITION_SIZE * 3 + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partitions = [
            partition_table.add_partition(size=MIN_PARTITION_SIZE)
            for _ in range(2)
        ]
        partition_ids = [partition.id for partition in partitions]
        name = factory.make_name("vg")
        vguuid = "%s" % uuid.uuid4()
        uri = get_volume_groups_uri(node)
        response = self.client.post(
            uri,
            {
                "name": name,
                "uuid": vguuid,
                "block_devices": block_device_ids,
                "partitions": partition_ids,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_volume_group = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_device_ids = [
            device["id"] for device in parsed_volume_group["devices"]
        ]
        self.assertEqual(parsed_volume_group.get("uuid"), vguuid)
        self.assertEqual(parsed_volume_group.get("name"), name)
        self.assertCountEqual(
            block_device_ids + partition_ids, parsed_device_ids
        )


class TestVolumeGroupAPI(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        volume_group = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/volume-group/%s/"
            % (node.system_id, volume_group.id),
            get_volume_group_uri(volume_group, node, False),
        )

    def test_read(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_ids = [bd.id for bd in block_devices]
        bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=bd
            )
            for bd in block_devices
        ]
        partitions = [
            factory.make_Partition(
                partition_table=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)
                )
            )
            for _ in range(3)
        ]
        partitions_ids = [partition.id for partition in partitions]
        partition_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition
            )
            for partition in partitions
        ]
        volume_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=bd_filesystems + partition_filesystems,
        )
        logical_volume_ids = [
            factory.make_VirtualBlockDevice(
                filesystem_group=volume_group, size=bd.size
            ).id
            for bd in block_devices
        ]
        uri = get_volume_group_uri(volume_group)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_volume_group = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_device_ids = [
            device["id"] for device in parsed_volume_group["devices"]
        ]
        parsed_logical_volume_ids = [
            lv["id"] for lv in parsed_volume_group["logical_volumes"]
        ]
        self.assertEqual(parsed_volume_group.get("id"), volume_group.id)
        self.assertEqual(parsed_volume_group.get("uuid"), volume_group.uuid)
        self.assertEqual(parsed_volume_group.get("name"), volume_group.name)
        self.assertEqual(
            parsed_volume_group.get("size"), volume_group.get_size()
        )
        self.assertEqual(
            parsed_volume_group.get("human_size"),
            human_readable_bytes(volume_group.get_size()),
        )
        self.assertEqual(
            parsed_volume_group.get("available_size"),
            volume_group.get_lvm_free_space(),
        )
        self.assertEqual(
            parsed_volume_group.get("human_available_size"),
            human_readable_bytes(volume_group.get_lvm_free_space()),
        )
        self.assertEqual(
            parsed_volume_group.get("used_size"),
            volume_group.get_lvm_allocated_size(),
        )
        self.assertEqual(
            parsed_volume_group.get("human_used_size"),
            human_readable_bytes(volume_group.get_lvm_allocated_size()),
        )
        self.assertEqual(
            parsed_volume_group.get("resource_uri"),
            get_volume_group_uri(volume_group, test_plural=False),
        )
        self.assertEqual(parsed_volume_group.get("system_id"), node.system_id)
        self.assertCountEqual(
            block_device_ids + partitions_ids, parsed_device_ids
        )
        self.assertCountEqual(logical_volume_ids, parsed_logical_volume_ids)

    def test_read_404_when_not_volume_group(self):
        not_volume_group = factory.make_FilesystemGroup(
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            )
        )
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.put(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.put(uri)
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_update_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node,
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            ),
        )
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.put(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update_updates_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        delete_block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            block_device=delete_block_device,
            filesystem_group=volume_group,
        )
        delete_bd_for_partition = factory.make_PhysicalBlockDevice(node=node)
        delete_table = factory.make_PartitionTable(
            block_device=delete_bd_for_partition
        )
        delete_partition = factory.make_Partition(partition_table=delete_table)
        factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV,
            partition=delete_partition,
            filesystem_group=volume_group,
        )
        new_name = factory.make_name("vg")
        new_uuid = "%s" % uuid.uuid4()
        new_block_device = factory.make_PhysicalBlockDevice(node=node)
        new_bd_for_partition = factory.make_PhysicalBlockDevice(node=node)
        new_table = factory.make_PartitionTable(
            block_device=new_bd_for_partition
        )
        new_partition = factory.make_Partition(partition_table=new_table)
        uri = get_volume_group_uri(volume_group)
        response = self.client.put(
            uri,
            {
                "name": new_name,
                "uuid": new_uuid,
                "add_block_devices": [new_block_device.id],
                "remove_block_devices": [delete_block_device.id],
                "add_partitions": [new_partition.id],
                "remove_partitions": [delete_partition.id],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        volume_group = reload_object(volume_group)
        self.assertEqual(new_name, volume_group.name)
        self.assertEqual(new_uuid, volume_group.uuid)
        self.assertEqual(
            volume_group.id,
            new_block_device.get_effective_filesystem().filesystem_group.id,
        )
        self.assertEqual(
            volume_group.id,
            new_partition.get_effective_filesystem().filesystem_group.id,
        )
        self.assertIsNone(delete_block_device.get_effective_filesystem())
        self.assertIsNone(delete_partition.get_effective_filesystem())

    def test_delete_deletes_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(volume_group))

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_delete_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node,
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            ),
        )
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_create_logical_volume_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {"op": "create_logical_volume"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_logical_volume_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {"op": "create_logical_volume"})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_create_logical_volume_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node,
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            ),
        )
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.post(uri, {"op": "create_logical_volume"})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_create_logical_volume_creates_logical_volume(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        name = factory.make_name("lv")
        vguuid = "%s" % uuid.uuid4()
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, volume_group.get_size())
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(
            uri,
            {
                "op": "create_logical_volume",
                "name": name,
                "uuid": vguuid,
                "size": size,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        logical_volume = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        expected_size = round_size_to_nearest_block(
            size, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(
            logical_volume.get("name"), f"{volume_group.name}-{name}"
        )
        self.assertEqual(logical_volume.get("uuid"), vguuid)
        self.assertEqual(logical_volume.get("size"), expected_size)

    def test_create_logical_volume_creates_max_logical_volume_if_size_empty(
        self,
    ):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        name = factory.make_name("lv")
        free_space = volume_group.get_lvm_free_space()
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(
            uri,
            {
                "op": "create_logical_volume",
                "name": name,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        logical_volume = response.json()
        expected_size = round_size_to_nearest_block(
            free_space, PARTITION_ALIGNMENT_SIZE, False
        )
        self.assertEqual(logical_volume.get("size"), expected_size)

    def test_delete_logical_volume_204_when_invalid_id(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        volume_id = random.randint(0, 100)
        response = self.client.post(
            uri, {"op": "delete_logical_volume", "id": volume_id}
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )

    def test_delete_logical_volume_400_when_missing_id(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(uri, {"op": "delete_logical_volume"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_delete_logical_volume_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        logical_volume = factory.make_VirtualBlockDevice(
            filesystem_group=volume_group
        )
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(
            uri, {"op": "delete_logical_volume", "id": logical_volume.id}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_logical_volume_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        volume_group = factory.make_VolumeGroup(node=node)
        logical_volume = factory.make_VirtualBlockDevice(
            filesystem_group=volume_group
        )
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(
            uri, {"op": "delete_logical_volume", "id": logical_volume.id}
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_delete_logical_volume_404_when_not_volume_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_volume_group = factory.make_FilesystemGroup(
            node=node,
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            ),
        )
        uri = get_volume_group_uri(not_volume_group)
        response = self.client.post(uri, {"op": "delete_logical_volume"})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_logical_volume_deletes_logical_volume(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        volume_group = factory.make_VolumeGroup(node=node)
        logical_volume = factory.make_VirtualBlockDevice(
            filesystem_group=volume_group
        )
        uri = get_volume_group_uri(volume_group)
        response = self.client.post(
            uri, {"op": "delete_logical_volume", "id": logical_volume.id}
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(logical_volume))
