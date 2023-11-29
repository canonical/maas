# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import json
import random
from uuid import uuid4

from django.conf import settings
from django.urls import reverse

from maasserver.enum import NODE_STATUS
from maasserver.models.partition import MIN_PARTITION_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import (
    json_load_bytes,
    round_size_to_nearest_block,
)
from maasserver.utils.orm import reload_object


def get_partitions_uri(block_device):
    """Return a BlockDevice's partitions URI on the API."""
    return reverse(
        "partitions_handler",
        args=[block_device.node_config.node.system_id, block_device.id],
    )


def get_partition_uri(partition, by_name=False):
    """Return a BlockDevice's partition URI on the API."""
    block_device = partition.partition_table.block_device
    node = block_device.node_config.node
    partition_id = partition.id
    if by_name:
        partition_id = partition.name
    ret = reverse(
        "partition_handler",
        args=[node.system_id, block_device.id, partition_id],
    )
    # Regression test for LP:1715230 - Both partitions and partition
    # API endpoints should work
    if random.choice([True, False]):
        ret = ret.replace("partitions", "partition")
    return ret


class TestPartitions(APITestCase.ForUser):
    def make_partition(self, node):
        device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        return factory.make_Partition(
            partition_table=partition_table, size=MIN_PARTITION_SIZE
        )

    def test_create_returns_403_if_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_size = 1024
        device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        factory.make_PartitionTable(block_device=device)
        uri = get_partitions_uri(device)

        # Add a partition to the start of the drive.
        size = round_size_to_nearest_block(
            random.randint(MIN_PARTITION_SIZE, MIN_PARTITION_SIZE * 2),
            block_size,
        )
        response = self.client.post(uri, {"size": size})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_returns_409_if_not_ready(self):
        self.become_admin()
        node = factory.make_Node(
            status=factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.READY])
        )
        block_size = 1024
        device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        factory.make_PartitionTable(block_device=device)
        uri = get_partitions_uri(device)

        # Add a partition to the start of the drive.
        size = round_size_to_nearest_block(
            random.randint(MIN_PARTITION_SIZE, MIN_PARTITION_SIZE * 2),
            block_size,
        )
        response = self.client.post(uri, {"size": size})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_create_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_size = 1024
        device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
            block_size=block_size,
        )
        factory.make_PartitionTable(block_device=device)
        uri = get_partitions_uri(device)

        # Add a partition to the start of the drive.
        size = round_size_to_nearest_block(
            random.randint(MIN_PARTITION_SIZE, MIN_PARTITION_SIZE * 2),
            block_size,
        )
        response = self.client.post(uri, {"size": size})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

    def test_list_partitions(self):
        device = factory.make_PhysicalBlockDevice(
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition1 = factory.make_Partition(
            partition_table=partition_table, size=MIN_PARTITION_SIZE
        )
        partition2 = factory.make_Partition(
            partition_table=partition_table, size=MIN_PARTITION_SIZE
        )
        uri = get_partitions_uri(device)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        partitions = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        p1 = [p for p in partitions if p["id"] == partition1.id][0]
        p2 = [p for p in partitions if p["id"] == partition2.id][0]
        self.assertEqual(partition1.size, p1["size"])
        self.assertEqual(partition1.uuid, p1["uuid"])
        self.assertEqual(partition2.size, p2["size"])
        self.assertEqual(partition2.uuid, p2["uuid"])

    def test_read_partition(self):
        device = factory.make_PhysicalBlockDevice(
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table,
            size=MIN_PARTITION_SIZE,
            bootable=True,
        )
        uri = get_partition_uri(partition)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_partition = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(parsed_partition.get("bootable"), True)
        self.assertEqual(parsed_partition.get("id"), partition.id)
        self.assertEqual(parsed_partition.get("size"), partition.size)
        self.assertEqual(
            parsed_partition.get("system_id"),
            device.node_config.node.system_id,
        )
        self.assertEqual(parsed_partition.get("device_id"), device.id)

    def test_read_partition_by_name(self):
        device = factory.make_PhysicalBlockDevice(
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table,
            size=MIN_PARTITION_SIZE,
            bootable=True,
        )
        uri = get_partition_uri(partition, by_name=True)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_partition = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertTrue(parsed_partition["bootable"])
        self.assertEqual(partition.id, parsed_partition["id"])
        self.assertEqual(partition.size, parsed_partition["size"])

    def test_read_partition_by_name_multiple(self):
        device = factory.make_PhysicalBlockDevice(
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE
        )
        partition_table = factory.make_PartitionTable(block_device=device)
        partition = factory.make_Partition(
            partition_table=partition_table,
            size=MIN_PARTITION_SIZE,
            bootable=True,
        )

        # a partition with same name on a different machine
        device2 = factory.make_PhysicalBlockDevice(name=device.name)
        partition_table2 = factory.make_PartitionTable(block_device=device2)
        partition2 = factory.make_Partition(partition_table=partition_table2)
        self.assertEqual(partition.get_name(), partition2.get_name())

        uri = get_partition_uri(partition, by_name=True)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_partition = response.json()
        self.assertEqual(partition.id, parsed_partition["id"])

    def test_delete_returns_403_for_non_admin(self):
        node = factory.make_Node(owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_returns_409_for_not_ready_node(self):
        self.become_admin()
        node = factory.make_Node(
            status=factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.READY])
        )
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_delete_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.delete(uri)

        # Returns no content and a 204 status_code.
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(partition))

    def test_delete_renumbers_others(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(block_device=device)
        p1 = partition_table.add_partition(size=MIN_PARTITION_SIZE)
        p2 = partition_table.add_partition(size=MIN_PARTITION_SIZE)
        p3 = partition_table.add_partition(size=MIN_PARTITION_SIZE)
        uri = get_partition_uri(p1)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertEqual(reload_object(p2).index, 1)
        self.assertEqual(reload_object(p3).index, 2)

    def test_format_returns_409_if_not_allocated_or_ready(self):
        self.become_admin()
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        fs_uuid = str(uuid4())
        fstype = factory.pick_filesystem_type()
        response = self.client.post(
            uri,
            {
                "op": "format",
                "uuid": fs_uuid,
                "fstype": fstype,
                "label": "mylabel",
            },
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_format_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        fs_uuid = str(uuid4())
        fstype = factory.pick_filesystem_type()
        response = self.client.post(
            uri,
            {
                "op": "format",
                "uuid": fs_uuid,
                "fstype": fstype,
                "label": "mylabel",
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_format_partition_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        fs_uuid = str(uuid4())
        fstype = factory.pick_filesystem_type()
        response = self.client.post(
            uri,
            {
                "op": "format",
                "uuid": fs_uuid,
                "fstype": fstype,
                "label": "mylabel",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        filesystem = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["filesystem"]
        self.assertEqual(fstype, filesystem["fstype"])
        self.assertEqual("mylabel", filesystem["label"])
        self.assertEqual(fs_uuid, filesystem["uuid"])

    def test_format_partition_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        fs_uuid = str(uuid4())
        fstype = factory.pick_filesystem_type()
        response = self.client.post(
            uri,
            {
                "op": "format",
                "uuid": fs_uuid,
                "fstype": fstype,
                "label": "mylabel",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        filesystem = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["filesystem"]
        self.assertEqual(fstype, filesystem["fstype"])
        self.assertEqual("mylabel", filesystem["label"])
        self.assertEqual(fs_uuid, filesystem["uuid"])

    def test_format_missing_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
        )
        factory.make_PartitionTable(block_device=device)
        partition_id = random.randint(1, 1000)  # Most likely a bogus one
        uri = reverse(
            "partition_handler", args=[node.system_id, device.id, partition_id]
        )
        fs_uuid = str(uuid4())
        fstype = factory.pick_filesystem_type()
        response = self.client.post(
            uri,
            {
                "op": "format",
                "uuid": fs_uuid,
                "fstype": fstype,
                "label": "mylabel",
            },
        )
        # Fails with a NOT_FOUND status.
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_format_partition_with_invalid_parameters(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.post(
            uri,
            {
                "op": "format",
                "uuid": "NOT A VALID UUID",
                "fstype": "FAT16",  # We don't support FAT16
                "label": "mylabel",
            },
        )
        # Fails with a BAD_REQUEST status.
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_unformat_returns_409_if_not_allocated_or_ready(self):
        self.become_admin()
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unformat"})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_unformat_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unformat"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_unformat_partition_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unformat"})
        # Returns the partition without the filesystem.
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        partition = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertIsNone(
            partition.get("filesystem"), "Partition still has a filesystem."
        )

    def test_unformat_partition_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition, acquired=True)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unformat"})
        # Returns the partition without the filesystem.
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        partition = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertIsNone(
            partition.get("filesystem"), "Partition still has a filesystem."
        )

    def test_unformat_missing_filesystem(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unformat"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_unformat_missing_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        device = factory.make_PhysicalBlockDevice(
            node=node,
            size=(MIN_PARTITION_SIZE * 4) + PARTITION_TABLE_EXTRA_SPACE,
        )
        factory.make_PartitionTable(block_device=device)
        partition_id = random.randint(1, 1000)  # Most likely a bogus one
        partition_id = random.randint(1, 1000)  # Most likely a bogus one
        uri = reverse(
            "partition_handler", args=[node.system_id, device.id, partition_id]
        )
        response = self.client.post(uri, {"op": "unformat"})
        # Returns nothing and a NOT_FOUND status.
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_mount_returns_409_if_not_allocated_or_ready(self):
        self.become_admin()
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = partition_table.add_partition()
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        mount_point = "/mnt"
        response = self.client.post(
            uri, {"op": "mount", "mount_point": mount_point}
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_mount_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = partition_table.add_partition()
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        mount_point = "/mnt"
        response = self.client.post(
            uri, {"op": "mount", "mount_point": mount_point}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_mount_sets_mount_path_on_filesystem_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = partition_table.add_partition()
        filesystem = factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        mount_point = "/mnt"
        mount_options = factory.make_name("mount-options")
        response = self.client.post(
            uri,
            {
                "op": "mount",
                "mount_point": mount_point,
                "mount_options": mount_options,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = response.json()
        self.assertEqual(
            parsed_device["filesystem"].get("mount_point"), mount_point
        )
        self.assertEqual(
            parsed_device["filesystem"].get("mount_options"), mount_options
        )
        fs = reload_object(filesystem)
        self.assertEqual(fs.mount_point, mount_point)
        self.assertEqual(fs.mount_options, mount_options)
        self.assertIs(fs.is_mounted, True)

    def test_mount_sets_mount_path_on_filesystem_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = partition_table.add_partition()
        filesystem = factory.make_Filesystem(
            partition=partition, acquired=True
        )
        uri = get_partition_uri(partition)
        mount_point = "/mnt"
        mount_options = factory.make_name("mount-options")
        response = self.client.post(
            uri,
            {
                "op": "mount",
                "mount_point": mount_point,
                "mount_options": mount_options,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            parsed_device["filesystem"].get("mount_point"), mount_point
        )
        self.assertEqual(
            parsed_device["filesystem"].get("mount_options"), mount_options
        )
        fs = reload_object(filesystem)
        self.assertEqual(fs.mount_point, mount_point)
        self.assertEqual(fs.mount_options, mount_options)
        self.assertIs(fs.is_mounted, True)

    def test_mount_returns_400_on_missing_mount_point(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "mount"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        parsed_error = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            {"mount_point": ["This field is required."]}, parsed_error
        )

    def test_unmount_returns_409_if_not_allocated_or_ready(self):
        self.become_admin()
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition, mount_point="/mnt")
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_unmount_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition, mount_point="/mnt")
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_unmount_returns_400_if_not_formatted(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "Partition is not formatted.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_unmount_returns_400_if_already_unmounted(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        factory.make_Filesystem(partition=partition)
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "Filesystem is already unmounted.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_unmount_unmounts_filesystem_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        partition = self.make_partition(node)
        filesystem = factory.make_Filesystem(
            partition=partition, mount_point="/mnt"
        )
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = response.json()
        self.assertIsNone(
            parsed_device["filesystem"].get("mount_point", object())
        )
        self.assertIsNone(
            parsed_device["filesystem"].get("mount_options", object())
        )
        fs = reload_object(filesystem)
        self.assertIsNone(fs.mount_point)
        self.assertIsNone(fs.mount_options)
        self.assertIs(fs.is_mounted, False)

    def test_unmount_unmounts_filesystem_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        filesystem = factory.make_Filesystem(
            partition=partition, mount_point="/mnt", acquired=True
        )
        uri = get_partition_uri(partition)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = response.json()
        self.assertIsNone(
            parsed_device["filesystem"].get("mount_point", object())
        )
        self.assertIsNone(
            parsed_device["filesystem"].get("mount_options", object())
        )
        fs = reload_object(filesystem)
        self.assertIsNone(fs.mount_point)
        self.assertIsNone(fs.mount_options)
        self.assertIs(fs.is_mounted, False)

    def test_add_tag_returns_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": factory.make_name("tag")}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_add_tag_to_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        tag_to_be_added = factory.make_name("tag")
        response = self.client.post(
            uri, {"op": "add_tag", "tag": tag_to_be_added}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_partition = json_load_bytes(response.content)
        self.assertIn(tag_to_be_added, parsed_partition["tags"])
        partition = reload_object(partition)
        self.assertIn(tag_to_be_added, partition.tags)

    def test_remove_tag_returns_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": factory.make_name("tag")}
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_remove_tag_from_block_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        partition = self.make_partition(node)
        uri = get_partition_uri(partition)
        tag_to_be_removed = partition.tags[0]
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": tag_to_be_removed}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_partition = json_load_bytes(response.content)
        self.assertNotIn(tag_to_be_removed, parsed_partition["tags"])
        partition = reload_object(partition)
        self.assertNotIn(tag_to_be_removed, partition.tags)
