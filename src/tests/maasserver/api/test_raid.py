# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import json
import uuid

from django.conf import settings
from django.urls import reverse

from maasserver.enum import FILESYSTEM_GROUP_TYPE, FILESYSTEM_TYPE, NODE_STATUS
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import RAID, RAID_SUPERBLOCK_OVERHEAD
from maasserver.models.partition import MIN_PARTITION_SIZE
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import reload_object

# Use the following block devices and partition sizes in these tests. This
# ensures that there will be enough space available to handle the partition
# table overhead and RAID overhead.
BLOCK_SIZE = MIN_BLOCK_DEVICE_SIZE * 2
PART_SIZE = MIN_PARTITION_SIZE * 2


def get_raid_devices_uri(node):
    """Return a Node's RAID devices URI on the API."""
    return reverse("raid_devices_handler", args=[node.system_id])


def get_raid_device_uri(raid, node=None):
    """Return a RAID device URI on the API."""
    if node is None:
        node = raid.get_node()
    return reverse("raid_device_handler", args=[node.system_id, raid.id])


def get_devices_from_raid(parsed_device):
    parsed_block_devices = [
        bd["id"] for bd in parsed_device["devices"] if bd["type"] == "physical"
    ]
    parsed_partitions = [
        part["id"]
        for part in parsed_device["devices"]
        if part["type"] == "partition"
    ]
    parsed_block_device_spares = [
        bd["id"]
        for bd in parsed_device["spare_devices"]
        if bd["type"] == "physical"
    ]
    parsed_partition_spares = [
        part["id"]
        for part in parsed_device["spare_devices"]
        if part["type"] == "partition"
    ]
    return (
        parsed_block_devices,
        parsed_partitions,
        parsed_block_device_spares,
        parsed_partition_spares,
    )


class TestRaidsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/raids/" % (node.system_id),
            get_raid_devices_uri(node),
        )

    def test_read(self):
        node = factory.make_Node()
        raids = [
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_0
            ),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_1
            ),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_5
            ),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
            ),
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_10
            ),
        ]
        # Not RAID. Should not be in the output.
        for _ in range(3):
            factory.make_FilesystemGroup(
                node=node, group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
            )
        uri = get_raid_devices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [raid.id for raid in raids]
        result_ids = [
            raid["id"]
            for raid in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        bds = [
            factory.make_PhysicalBlockDevice(
                node=node, size=(BLOCK_SIZE * 2) + PARTITION_TABLE_EXTRA_SPACE
            )
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [bd.id for bd in bds[:5]]
        partitions = [
            bd.get_partitiontable().add_partition(size=PART_SIZE).id
            for bd in bds[5:]
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_0,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        bds = [
            factory.make_PhysicalBlockDevice(
                node=node, size=(BLOCK_SIZE * 2) + PARTITION_TABLE_EXTRA_SPACE
            )
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [bd.id for bd in bds[:5]]
        partitions = [
            bd.get_partitiontable().add_partition(size=PART_SIZE).id
            for bd in bds[5:]
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_0,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_create_raid_0(self):
        """Checks it's possible to create a RAID 0 using with 5 raw devices, 5
        partitions and no spare."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        bds = [
            factory.make_PhysicalBlockDevice(
                node=node, size=(BLOCK_SIZE * 2) + PARTITION_TABLE_EXTRA_SPACE
            )
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [bd.id for bd in bds[:5]]
        partitions = [
            bd.get_partitiontable().add_partition(size=PART_SIZE).id
            for bd in bds[5:]
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_0,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        (
            parsed_block_devices,
            parsed_partitions,
            parsed_block_device_spares,
            parsed_partition_spares,
        ) = get_devices_from_raid(parsed_device)
        raid = RAID.objects.get(id=parsed_device["id"])
        self.assertEqual(parsed_device["size"], raid.get_size())
        self.assertEqual(uuid4, parsed_device["uuid"])
        self.assertCountEqual(block_devices, parsed_block_devices)
        self.assertCountEqual(partitions, parsed_partitions)
        self.assertEqual([], parsed_block_device_spares)
        self.assertEqual([], parsed_partition_spares)

    def test_create_raid_0_with_a_spare_fails(self):
        """Checks it's not possible to create a RAID 0 using 4 raw
        devices, 5 partitions and one spare device (because a RAID-0 cannot
        have spares)."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        bds = [
            factory.make_PhysicalBlockDevice(
                node=node, size=(BLOCK_SIZE * 2) + PARTITION_TABLE_EXTRA_SPACE
            )
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [
            bd.id for bd in bds[1:] if bd.get_partitiontable() is None
        ]
        partitions = [
            bd.get_partitiontable().add_partition(size=PART_SIZE).id
            for bd in bds[5:]
        ]
        uuid4 = factory.make_UUID()
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_0,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": [bds[0].id],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_1(self):
        """Checks it's possible to create a RAID 1 using with 5 raw devices, 5
        partitions and no spare."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        bds = [
            factory.make_PhysicalBlockDevice(
                node=node, size=(BLOCK_SIZE * 2) + PARTITION_TABLE_EXTRA_SPACE
            )
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        block_devices = [bd.id for bd in bds[:5]]
        partitions = [
            bd.get_partitiontable().add_partition(size=PART_SIZE).id
            for bd in bds[5:]
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_1,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        (
            parsed_block_devices,
            parsed_partitions,
            parsed_block_device_spares,
            parsed_partition_spares,
        ) = get_devices_from_raid(parsed_device)
        self.assertEqual(
            PART_SIZE - RAID_SUPERBLOCK_OVERHEAD, parsed_device["size"]
        )
        self.assertEqual(uuid4, parsed_device["uuid"])
        self.assertCountEqual(block_devices, parsed_block_devices)
        self.assertCountEqual(partitions, parsed_partitions)
        self.assertEqual([], parsed_block_device_spares)
        self.assertEqual([], parsed_partition_spares)

    def test_create_raid_1_with_spares(self):
        """Checks it's possible to create a RAID 1 using with 4 raw devices, 4
        partitions and two spares."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        bds = [
            factory.make_PhysicalBlockDevice(
                node=node, size=(BLOCK_SIZE * 2) + PARTITION_TABLE_EXTRA_SPACE
            )
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        large_partitions = [
            bd.get_partitiontable().add_partition(size=PART_SIZE)
            for bd in bds[5:]
        ]
        block_devices = [bd.id for bd in bds[1:5]]
        partitions = [lp.id for lp in large_partitions[1:]]
        spare_devices = [bds[0].id]
        spare_partitions = [large_partitions[0].id]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_1,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": spare_devices,
                "spare_partitions": spare_partitions,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        (
            parsed_block_devices,
            parsed_partitions,
            parsed_block_device_spares,
            parsed_partition_spares,
        ) = get_devices_from_raid(parsed_device)
        self.assertEqual(
            PART_SIZE - RAID_SUPERBLOCK_OVERHEAD, parsed_device["size"]
        )
        self.assertEqual(uuid4, parsed_device["uuid"])
        self.assertCountEqual(block_devices, parsed_block_devices)
        self.assertCountEqual(partitions, parsed_partitions)
        self.assertEqual(spare_devices, parsed_block_device_spares)
        self.assertEqual(spare_partitions, parsed_partition_spares)

    def test_create_raid_5(self):
        """Checks it's possible to create a RAID 5 using 4 raw 10TB
        devices, 4 9TB partitions, one spare device and one spare partition."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 10 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        for bd in bds[5:]:
            bd.get_partitiontable().add_partition(size=1000**4)
        large_partitions = [
            bd.get_partitiontable().add_partition() for bd in bds[5:]
        ]
        block_devices = [
            bd.id for bd in bds[1:] if bd.get_partitiontable() is None
        ]
        partitions = [lp.id for lp in large_partitions[1:]]
        spare_devices = [bds[0].id]
        spare_partitions = [large_partitions[0].id]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_5,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": spare_devices,
                "spare_partitions": spare_partitions,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        (
            parsed_block_devices,
            parsed_partitions,
            parsed_block_device_spares,
            parsed_partition_spares,
        ) = get_devices_from_raid(parsed_device)
        # Size is equivalent to 7 of the smallest device (the partitions).
        self.assertEqual(
            (7 * large_partitions[0].size) - RAID_SUPERBLOCK_OVERHEAD,
            parsed_device["size"],
        )
        self.assertCountEqual(block_devices, parsed_block_devices)
        self.assertCountEqual(partitions, parsed_partitions)
        self.assertEqual(spare_devices, parsed_block_device_spares)
        self.assertEqual(spare_partitions, parsed_partition_spares)

    def test_create_raid_6(self):
        """Checks it's possible to create a RAID 6 using 4 raw
        devices, 4 partitions, one spare device and one spare partition."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 10 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        for bd in bds[5:]:
            bd.get_partitiontable().add_partition(size=1000**4)
        large_partitions = [
            bd.get_partitiontable().add_partition() for bd in bds[5:]
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        block_devices = [
            bd.id for bd in bds[1:] if bd.get_partitiontable() is None
        ]
        partitions = [lp.id for lp in large_partitions[1:]]
        spare_devices = [bds[0].id]
        spare_partitions = [large_partitions[0].id]
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_6,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": spare_devices,
                "spare_partitions": spare_partitions,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        (
            parsed_block_devices,
            parsed_partitions,
            parsed_block_device_spares,
            parsed_partition_spares,
        ) = get_devices_from_raid(parsed_device)
        # Size is equivalent to 6 of the smallest device (the partitions).
        self.assertEqual(
            (6 * large_partitions[0].size) - RAID_SUPERBLOCK_OVERHEAD,
            parsed_device["size"],
        )
        self.assertCountEqual(block_devices, parsed_block_devices)
        self.assertCountEqual(partitions, parsed_partitions)
        self.assertEqual(spare_devices, parsed_block_device_spares)
        self.assertEqual(spare_partitions, parsed_partition_spares)

    def test_create_raid_10(self):
        """Checks it's possible to create a RAID 10 using 4 raw
        devices, 4 partitions, one spare device and one spare partition."""
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 10 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(10)
        ]
        for bd in bds[5:]:
            factory.make_PartitionTable(block_device=bd)
        for bd in bds[5:]:
            bd.get_partitiontable().add_partition(size=1000**4)
        large_partitions = [
            bd.get_partitiontable().add_partition() for bd in bds[5:]
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        block_devices = [
            bd.id for bd in bds[1:] if bd.get_partitiontable() is None
        ]
        partitions = [lp.id for lp in large_partitions[1:]]
        spare_devices = [bds[0].id]
        spare_partitions = [large_partitions[0].id]
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_10,
                "block_devices": block_devices,
                "partitions": partitions,
                "spare_devices": spare_devices,
                "spare_partitions": spare_partitions,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        (
            parsed_block_devices,
            parsed_partitions,
            parsed_block_device_spares,
            parsed_partition_spares,
        ) = get_devices_from_raid(parsed_device)
        # Size is equivalent to 4 of the smallest device (the partitions).
        self.assertEqual(
            (4 * large_partitions[0].size) - RAID_SUPERBLOCK_OVERHEAD,
            parsed_device["size"],
        )
        self.assertCountEqual(block_devices, parsed_block_devices)
        self.assertCountEqual(partitions, parsed_partitions)
        self.assertEqual(spare_devices, parsed_block_device_spares)
        self.assertEqual(spare_partitions, parsed_partition_spares)

    def test_create_raid_5_with_2_elements_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 2 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(2)
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_5,
                "block_devices": [bd.id for bd in bds],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_6_with_3_elements_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 3 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(3)
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_6,
                "block_devices": [bd.id for bd in bds],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_10_with_2_elements_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 3 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(2)
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_10,
                "block_devices": [bd.id for bd in bds],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_0_with_one_element_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add one 10TB physical block devices to the node.
        bd = factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_0,
                "block_devices": [bd.id],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_1_with_one_element_fails_without_side_effects(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add one 10TB physical block devices to the node.
        bd = factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_1,
                "block_devices": [bd.id],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertIsNone(bd.get_effective_filesystem())

    def test_create_raid_with_invalid_block_device_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add no block devices to the node and, instead, invent a couple
        # non-existing block devices.
        ids = list(range(1000, 1010))
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_5,
                "block_devices": ids,
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_with_invalid_partition_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add no partitions to the node and, instead, invent a couple
        # non-existing partitions.
        ids = list(range(1000, 1010))
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_5,
                "block_devices": [],
                "partitions": ids,
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_raid_with_invalid_spare_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        # Add 10 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**4)
            for i in range(10)
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_6,
                "block_devices": [bd.id for bd in bds],
                "partitions": [],
                "spare_devices": [1000, 1001],  # Two non-existing spares.
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        for bd in bds:
            self.assertIsNone(bd.get_effective_filesystem())

    def test_create_raid_with_block_device_from_other_node_fails(self):
        self.become_admin()
        node1 = factory.make_Node(status=NODE_STATUS.READY)
        node2 = factory.make_Node(status=NODE_STATUS.READY)
        # Add 10 10TB physical block devices to the node.
        bds = [
            factory.make_PhysicalBlockDevice(node=node2, size=10 * 1000**4)
            for i in range(10)
        ]
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node1)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_6,
                "block_devices": [bd.id for bd in bds],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        for bd in bds:
            self.assertIsNone(bd.get_effective_filesystem())

    def test_create_raid_without_any_element_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uuid4 = str(uuid.uuid4())
        uri = get_raid_devices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "md0",
                "uuid": uuid4,
                "level": FILESYSTEM_GROUP_TYPE.RAID_6,
                "block_devices": [],
                "partitions": [],
                "spare_devices": [],
                "spare_partitions": [],
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestRaidAPI(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_0
        )
        self.assertEqual(
            f"/MAAS/api/2.0/nodes/{node.system_id}/raid/{raid.id}/",
            get_raid_device_uri(raid, node=node),
        )

    def test_read(self):
        node = factory.make_Node()
        block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        block_device_ids = [bd.id for bd in block_devices]
        bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID, block_device=bd
            )
            for bd in block_devices
        ]
        spare_block_devices = [
            factory.make_PhysicalBlockDevice(node=node) for _ in range(3)
        ]
        spare_block_device_ids = [bd.id for bd in spare_block_devices]
        spare_bd_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE, block_device=bd
            )
            for bd in spare_block_devices
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
                fstype=FILESYSTEM_TYPE.RAID, partition=partition
            )
            for partition in partitions
        ]
        spare_partitions = [
            factory.make_Partition(
                partition_table=factory.make_PartitionTable(
                    block_device=factory.make_PhysicalBlockDevice(node=node)
                )
            )
            for _ in range(3)
        ]
        spare_partitions_ids = [partition.id for partition in spare_partitions]
        spare_partition_filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.RAID_SPARE, partition=partition
            )
            for partition in spare_partitions
        ]
        raid = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_5,
            filesystems=(
                bd_filesystems
                + spare_bd_filesystems
                + partition_filesystems
                + spare_partition_filesystems
            ),
        )
        uri = get_raid_device_uri(raid)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_raid = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_device_ids = [device["id"] for device in parsed_raid["devices"]]
        parsed_spare_device_ids = [
            device["id"] for device in parsed_raid["spare_devices"]
        ]
        self.assertEqual(parsed_raid.get("id"), raid.id)
        self.assertEqual(parsed_raid.get("uuid"), raid.uuid)
        self.assertEqual(parsed_raid.get("name"), raid.name)
        self.assertEqual(parsed_raid.get("level"), raid.group_type)
        self.assertEqual(parsed_raid.get("size"), raid.get_size())
        self.assertEqual(
            parsed_raid.get("human_size"),
            human_readable_bytes(raid.get_size()),
        )
        self.assertEqual(
            parsed_raid.get("resource_uri"), get_raid_device_uri(raid)
        )
        self.assertEqual(parsed_raid.get("system_id"), node.system_id)
        self.assertCountEqual(
            block_device_ids + partitions_ids, parsed_device_ids
        )
        self.assertCountEqual(
            spare_block_device_ids + spare_partitions_ids,
            parsed_spare_device_ids,
        )
        self.assertEqual(
            raid.virtual_device.id, parsed_raid["virtual_device"]["id"]
        )

    def test_read_404_when_not_raid(self):
        not_raid = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        uri = get_raid_device_uri(not_raid)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_rename_raid(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_5
        )
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"name": "raid0"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual("raid0", parsed_device["name"])

    def test_change_raid_uuid(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        uuid4 = str(uuid.uuid4())
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"uuid": uuid4})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(uuid4, parsed_device["uuid"])

    def test_add_valid_blockdevice(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"add_block_devices": [device.id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new device is now part of the array.
        self.assertIn(
            device.id,
            [
                bd["id"]
                for bd in parsed_device["devices"]
                if bd["type"] == "physical"
                and bd["filesystem"]["fstype"] == FILESYSTEM_TYPE.RAID
            ],
        )
        self.assertEqual(
            FILESYSTEM_TYPE.RAID, device.get_effective_filesystem().fstype
        )

    def test_remove_valid_blockdevice(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice(node=node)
        Filesystem.objects.create(
            node_config=node.current_config,
            block_device=device,
            filesystem_group=raid,
            fstype=FILESYSTEM_TYPE.RAID,
        )
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"remove_block_devices": [device.id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new device is not part of the array.
        self.assertNotIn(
            device.id,
            [
                bd["id"]
                for bd in parsed_device["devices"]
                if bd["type"] == "physical"
                and bd["filesystem"]["fstype"] == FILESYSTEM_TYPE.RAID
            ],
        )
        self.assertIsNone(device.get_effective_filesystem())

    def test_add_valid_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(node=node)
        ).add_partition()
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"add_partitions": [partition.id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new partition is now part of the array.
        self.assertIn(
            partition.id,
            [
                p["id"]
                for p in parsed_device["devices"]
                if p["type"] == "partition"
                and p["filesystem"]["fstype"] == FILESYSTEM_TYPE.RAID
            ],
        )

    def test_remove_valid_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(node=node)
        ).add_partition()
        Filesystem.objects.create(
            node_config=node.current_config,
            partition=partition,
            filesystem_group=raid,
            fstype=FILESYSTEM_TYPE.RAID,
        )
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"remove_partitions": [partition.id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new device is not part of the array.
        self.assertNotIn(
            partition.id,
            [
                bd["id"]
                for bd in parsed_device["spare_devices"]
                if bd["type"] == "partition"
                and bd["filesystem"]["fstype"] == FILESYSTEM_TYPE.RAID
            ],
        )
        self.assertIsNone(partition.get_effective_filesystem())

    def test_add_valid_spare_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"add_spare_devices": [device.id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new device is now part of the array.
        self.assertIn(
            device.id,
            [
                bd["id"]
                for bd in parsed_device["spare_devices"]
                if bd["type"] == "physical"
            ],
        )

    def test_remove_valid_spare_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice(node=node)
        Filesystem.objects.create(
            node_config=node.current_config,
            block_device=device,
            filesystem_group=raid,
            fstype=FILESYSTEM_TYPE.RAID_SPARE,
        )
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"remove_spare_devices": [device.id]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new device is not part of the array.
        self.assertNotIn(
            device.id,
            [
                bd["id"]
                for bd in parsed_device["spare_devices"]
                if bd["type"] == "physical"
                and bd["filesystem"]["fstype"] == FILESYSTEM_TYPE.RAID_SPARE
            ],
        )

    def test_add_valid_spare_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(node=node)
        ).add_partition()
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(
            uri, {"add_spare_partitions": [partition.id]}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new partition is now part of the array.
        self.assertIn(
            partition.id,
            [
                p["id"]
                for p in parsed_device["spare_devices"]
                if p["type"] == "partition"
            ],
        )

    def test_remove_valid_spare_partition(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice(node=node)
        ).add_partition()
        Filesystem.objects.create(
            node_config=node.current_config,
            partition=partition,
            filesystem_group=raid,
            fstype=FILESYSTEM_TYPE.RAID_SPARE,
        )
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(
            uri, {"remove_spare_partitions": [partition.id]}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # Makes sure our new device is not part of the array.
        self.assertNotIn(
            partition.id,
            [
                bd["id"]
                for bd in parsed_device["spare_devices"]
                if bd["type"] == "partition"
                and bd["filesystem"]["fstype"] == FILESYSTEM_TYPE.RAID_SPARE
            ],
        )

    def test_add_invalid_blockdevice_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice()  # From another node.
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"add_block_devices": [device.id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertIsNone(device.get_effective_filesystem())

    def test_remove_invalid_blockdevice_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice()  # From another node.
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"remove_block_devices": [device.id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_add_invalid_partition_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice()
        ).add_partition()
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"add_partitions": [partition.id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_remove_invalid_partition_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice()
        ).add_partition()
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"remove_partitions": [partition.id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_add_invalid_spare_device_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice()  # From another node.
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"add_spare_devices": [device.id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertIsNone(device.get_effective_filesystem())

    def test_remove_invalid_spare_device_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        device = factory.make_PhysicalBlockDevice()  # From another node.
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(uri, {"remove_spare_devices": [device.id]})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_add_invalid_spare_partition_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        # Make a partition on a block device on another node.
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice()
        ).add_partition()
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(
            uri, {"add_spare_partitions": [partition.id]}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertIsNone(partition.get_effective_filesystem())

    def test_remove_invalid_spare_partition_fails(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_6
        )
        # Make a partition on a block device on another node.
        partition = factory.make_PartitionTable(
            block_device=factory.make_PhysicalBlockDevice()
        ).add_partition()
        uri = get_raid_device_uri(raid, node)
        response = self.client.put(
            uri, {"remove_spare_partitions": [partition.id]}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_delete_deletes_raid(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.RAID_5
        )
        uri = get_raid_device_uri(raid)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(raid))

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        raid = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.RAID_6, node=node
        )
        uri = get_raid_device_uri(raid)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_404_when_not_raid(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        not_raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        uri = get_raid_device_uri(not_raid)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_409_when_not_ready(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        not_raid = factory.make_FilesystemGroup(
            node=node, group_type=FILESYSTEM_GROUP_TYPE.BCACHE
        )
        uri = get_raid_device_uri(not_raid)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
