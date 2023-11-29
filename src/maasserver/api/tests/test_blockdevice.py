# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import uuid

from django.conf import settings
from django.urls import reverse

from maasserver.enum import FILESYSTEM_GROUP_TYPE, FILESYSTEM_TYPE, NODE_STATUS
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


def get_blockdevices_uri(node):
    """Return a Node's BlockDevice URI on the API."""
    return reverse("blockdevices_handler", args=[node.system_id])


def get_blockdevice_uri(device, node=None, by_name=False):
    """Return a BlockDevice's URI on the API."""
    if node is None:
        node = device.node_config.node
    device_id = device.id
    if by_name:
        device_id = device.name
    return reverse("blockdevice_handler", args=[node.system_id, device_id])


class TestBlockDevices(APITestCase.ForUser):
    def test_read(self):
        node = factory.make_Node(with_boot_disk=False)

        # Add three physical block devices
        physical_block_devices = [
            factory.make_PhysicalBlockDevice(node=node, size=10 * 1000**3)
            for _ in range(3)
        ]

        # Partition and add a LVM_PV filesystem to the last two physical block
        # devices. Leave the first partition alone.
        lvm_pv_filesystems = [
            factory.make_Filesystem(
                block_device=device, fstype=FILESYSTEM_TYPE.LVM_PV
            )
            for device in physical_block_devices[1:]
        ]

        # Make a filesystem_group (analogous to a volume group) on top of our
        # two lvm-pm filesystems.
        filesystem_group = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=lvm_pv_filesystems,
        )

        # Make a VirtualBlockDevice on top of the filesystem group we just
        # made.
        virtual_block_device = factory.make_VirtualBlockDevice(
            filesystem_group=filesystem_group, size=10 * 1000**3
        )

        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        devices = json_load_bytes(response.content)

        # We should have 4 devices, three physical and one virtual
        self.assertEqual(len(devices), 4)
        self.assertEqual(
            len([d for d in devices if d["type"] == "physical"]), 3
        )
        self.assertEqual(
            len([d for d in devices if d["type"] == "virtual"]), 1
        )

        # The IDs we expect and the IDs we got through the API should match.
        expected_device_ids = [
            d.id for d in physical_block_devices + [virtual_block_device]
        ]
        result_device_ids = [d["id"] for d in devices]
        self.assertCountEqual(expected_device_ids, result_device_ids)
        # Validate that every one has a resource_uri.
        for d in devices:
            self.assertIn(
                "resource_uri",
                d,
                f"Device({d['type']}:{d['id']} is missing a resource_uri.",
            )

    def test_read_returns_model(self):
        node = factory.make_Node(with_boot_disk=False)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)
        self.assertEqual(parsed_devices[0]["model"], block_device.model)

    def test_read_returns_filesystem(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        filesystem = factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)
        fsdata = parsed_devices[1]["filesystem"]
        self.assertEqual(fsdata["fstype"], filesystem.fstype)
        self.assertEqual(fsdata["uuid"], filesystem.uuid)
        self.assertEqual(fsdata["mount_point"], filesystem.mount_point)

    def test_read_returns_storage_pool(self):
        node = factory.make_Node(with_boot_disk=False)
        vm = factory.make_VirtualMachine(machine=node)
        pool = factory.make_PodStoragePool()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_VirtualMachineDisk(
            vm, backing_pool=pool, block_device=block_device
        )

        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)
        self.assertEqual(parsed_devices[0]["storage_pool"], pool.pool_id)

    def test_read_returns_numa_node(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_NUMANode(node=node)
        numa_node2 = factory.make_NUMANode(node=node)
        factory.make_PhysicalBlockDevice(numa_node=numa_node2)

        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        [parsed_device] = json_load_bytes(response.content)
        self.assertEqual(parsed_device["numa_node"], 2)

    def test_read_no_numa_node_not_physical(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)
        [parsed_device] = [
            device for device in parsed_devices if device["type"] != "physical"
        ]
        self.assertIsNone(parsed_device["numa_node"])

    def test_read_returns_partition_type(self):
        node = factory.make_Node(with_boot_disk=False)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )

        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)

        self.assertEqual(
            parsed_devices[0]["partition_table_type"],
            partition_table.table_type,
        )

    def test_read_returns_partitions(self):
        node = factory.make_Node(with_boot_disk=False)
        block_size = 1024
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=1000000 * block_size
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type="MBR"
        )
        # Use PartitionTable methods that auto-size and position partitions
        partition1 = partition_table.add_partition(size=50000 * block_size)
        partition2 = partition_table.add_partition()

        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)

        self.assertEqual(parsed_devices[0]["partition_table_type"], "MBR")
        self.assertEqual(len(parsed_devices[0]["partitions"]), 2)

        # We should have one device
        self.assertEqual(len(parsed_devices), 1)
        [parsed_device] = parsed_devices
        # Verify the two partitions created above have the expected sizes
        self.assertIn(
            partition1.size, [p["size"] for p in parsed_device["partitions"]]
        )
        self.assertIn(
            partition2.size, [p["size"] for p in parsed_device["partitions"]]
        )

    def test_read_returns_filesystems_on_partitions(self):
        node = factory.make_Node(with_boot_disk=False)
        block_size = 1024
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=1000000 * block_size
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type="MBR"
        )
        # Use PartitionTable methods that auto-size and position partitions
        partition1 = partition_table.add_partition(size=50000 * block_size)
        partition2 = partition_table.add_partition()
        filesystem1 = factory.make_Filesystem(partition=partition1)
        filesystem2 = factory.make_Filesystem(partition=partition2)
        uri = get_blockdevices_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_devices = json_load_bytes(response.content)

        # We should have one device
        self.assertEqual(len(parsed_devices), 1)
        [parsed_device] = parsed_devices
        # Check whether the filesystems are what we expect them to be
        self.assertEqual(
            parsed_device["partitions"][0]["filesystem"]["uuid"],
            filesystem1.uuid,
        )
        self.assertEqual(
            parsed_device["partitions"][1]["filesystem"]["uuid"],
            filesystem2.uuid,
        )

    def test_create_physicalblockdevice_as_normal_user(self):
        """Physical block device creation should fail for normal user"""
        node = factory.make_Node()
        uri = get_blockdevices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "sda",
                "block_size": 1024,
                "size": 140 * 1024,
                "path": "/dev/sda",
                "model": "A2M0003",
                "serial": "42",
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_physicalblockdevice_as_admin(self):
        """Checks it's possible to add a physical block device using the POST
        method"""
        self.become_admin()
        node = factory.make_Node(with_boot_disk=False)
        uri = get_blockdevices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "sda",
                "block_size": 1024,
                "size": MIN_BLOCK_DEVICE_SIZE,
                "path": "/dev/sda",
                "model": "A2M0003",
                "serial": "42",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        reload_object(node)
        pbd = node.physicalblockdevice_set.first()
        self.assertEqual(pbd.node_config.node_id, node.id)
        self.assertEqual(pbd.name, "sda")
        self.assertEqual(pbd.block_size, 1024)
        self.assertEqual(pbd.size, MIN_BLOCK_DEVICE_SIZE)
        self.assertEqual(pbd.path, "/dev/disk/by-dname/sda")
        self.assertEqual(pbd.model, "A2M0003")
        self.assertEqual(pbd.serial, "42")

    def test_create_physicalblockdevice_with_invalid_params(self):
        """Checks whether an invalid parameter results in a BAD_REQUEST"""
        self.become_admin()
        node = factory.make_Node()
        uri = get_blockdevices_uri(node)
        response = self.client.post(
            uri,
            {
                "name": "sda",
                "block_size": 1024,
                "size": 100 * 1024,
                "path": "/dev/sda",
                "model": "A2M0003",
                "serial": "42",
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestBlockDeviceAPI(APITestCase.ForUser):
    def test_read_physical_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(block_device)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(block_device.id, parsed_device["id"])
        self.assertEqual("physical", parsed_device["type"])
        self.assertEqual(
            get_blockdevice_uri(block_device), parsed_device["resource_uri"]
        )

    def test_read_block_device_by_name(self):
        block_device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(block_device, by_name=True)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(block_device.id, parsed_device["id"])

    def test_read_virtual_block_device(self):
        block_device = factory.make_VirtualBlockDevice()
        uri = get_blockdevice_uri(block_device)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(block_device.id, parsed_device["id"])
        self.assertEqual(block_device.get_name(), parsed_device["name"])
        self.assertEqual("virtual", parsed_device["type"])
        self.assertEqual(
            get_blockdevice_uri(block_device), parsed_device["resource_uri"]
        )

    def test_read_returns_filesystem(self):
        block_device = factory.make_PhysicalBlockDevice()
        filesystem = factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(
            parsed_device["filesystem"]["fstype"], filesystem.fstype
        )
        self.assertEqual(parsed_device["filesystem"]["uuid"], filesystem.uuid)
        self.assertEqual(
            parsed_device["filesystem"]["mount_point"], filesystem.mount_point
        )
        self.assertEqual(
            parsed_device["filesystem"]["mount_options"],
            filesystem.mount_options,
        )

    def test_read_returns_partitions(self):
        node = factory.make_Node()
        block_size = 1024
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=1000000 * block_size
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type="MBR"
        )
        # Use PartitionTable methods that auto-size and position partitions
        partition1 = partition_table.add_partition(size=50000 * block_size)
        partition2 = partition_table.add_partition()
        uri = get_blockdevice_uri(block_device)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        partition1_details = parsed_device["partitions"][0]
        self.assertEqual(
            partition1_details.get("bootable"), partition1.bootable
        )
        self.assertEqual(partition1_details.get("id"), partition1.id)
        self.assertEqual(partition1_details.get("size"), partition1.size)
        self.assertEqual(partition1_details.get("uuid"), partition1.uuid)
        partition2_details = parsed_device["partitions"][1]
        self.assertEqual(
            partition2_details.get("bootable"), partition2.bootable
        )
        self.assertEqual(partition2_details.get("id"), partition2.id)
        self.assertEqual(partition2_details.get("size"), partition2.size)
        self.assertEqual(partition2_details.get("uuid"), partition2.uuid)

    def test_read_returns_filesytems_on_partitions(self):
        node = factory.make_Node()
        block_size = 1024
        block_device = factory.make_PhysicalBlockDevice(
            node=node, size=1000000 * block_size
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device, table_type="MBR"
        )
        # Use PartitionTable methods that auto-size and position partitions
        partition1 = partition_table.add_partition(size=50000 * block_size)
        partition2 = partition_table.add_partition()
        filesystem1 = factory.make_Filesystem(
            partition=partition1, fstype=FILESYSTEM_TYPE.EXT4
        )
        filesystem2 = factory.make_Filesystem(
            partition=partition2, fstype=FILESYSTEM_TYPE.EXT2
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(
            {
                "fstype": filesystem1.fstype,
                "label": filesystem1.label,
                "uuid": filesystem1.uuid,
                "mount_point": filesystem1.mount_point,
                "mount_options": filesystem1.mount_options,
            },
            parsed_device["partitions"][0]["filesystem"],
        )
        self.assertEqual(
            {
                "fstype": filesystem2.fstype,
                "label": filesystem2.label,
                "uuid": filesystem2.uuid,
                "mount_point": filesystem2.mount_point,
                "mount_options": filesystem2.mount_options,
            },
            parsed_device["partitions"][1]["filesystem"],
        )

    def test_read_returns_system_id(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.OK)
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(parsed_device.get("system_id"), node.system_id)

    def test_delete_returns_403_when_not_admin(self):
        block_device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(block_device)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_returns_404_when_system_id_doesnt_match(self):
        self.become_admin()
        block_device = factory.make_PhysicalBlockDevice()
        other_node = factory.make_Node()
        uri = get_blockdevice_uri(block_device, node=other_node)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_returns_409_when_the_nodes_not_ready(self):
        self.become_admin()
        node = factory.make_Node(
            status=factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.READY])
        )
        block_device = factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_delete_deletes_block_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(block_device))

    def test_add_tag_returns_403_when_not_admin(self):
        block_device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": factory.make_name("tag")}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_add_tag_returns_404_when_system_id_doesnt_match(self):
        self.become_admin()
        block_device = factory.make_PhysicalBlockDevice()
        other_node = factory.make_Node()
        uri = get_blockdevice_uri(block_device, node=other_node)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": factory.make_name("tag")}
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_add_tag_returns_409_when_the_nodes_not_ready(self):
        self.become_admin()
        node = factory.make_Node(
            status=factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.READY])
        )
        block_device = factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": factory.make_name("tag")}
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_add_tag_to_block_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        tag_to_be_added = factory.make_name("tag")
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": tag_to_be_added}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertIn(tag_to_be_added, parsed_device["tags"])
        block_device = reload_object(block_device)
        self.assertIn(tag_to_be_added, block_device.tags)

    def test_remove_tag_returns_403_when_not_admin(self):
        block_device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": factory.make_name("tag")}
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_remove_tag_returns_404_when_system_id_doesnt_match(self):
        self.become_admin()
        block_device = factory.make_PhysicalBlockDevice()
        other_node = factory.make_Node()
        uri = get_blockdevice_uri(block_device, node=other_node)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": factory.make_name("tag")}
        )

        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_remove_tag_returns_409_when_the_nodes_not_ready(self):
        self.become_admin()
        node = factory.make_Node(
            status=factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.READY])
        )
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": factory.make_name("tag")}
        )

        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_remove_tag_from_block_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        tag_to_be_removed = block_device.tags[0]
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": tag_to_be_removed}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertNotIn(tag_to_be_removed, parsed_device["tags"])
        block_device = reload_object(block_device)
        self.assertNotIn(tag_to_be_removed, block_device.tags)

    def test_format_returns_409_if_not_allocated_or_ready(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        fstype = factory.pick_filesystem_type()
        fsuuid = "%s" % uuid.uuid4()
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "format", "fstype": fstype, "uuid": fsuuid}
        )
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_format_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        fstype = factory.pick_filesystem_type()
        fsuuid = "%s" % uuid.uuid4()
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "format", "fstype": fstype, "uuid": fsuuid}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_format_formats_block_device_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        fstype = factory.pick_filesystem_type()
        fsuuid = "%s" % uuid.uuid4()
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "format", "fstype": fstype, "uuid": fsuuid}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(parsed_device["filesystem"]["fstype"], fstype)
        self.assertEqual(parsed_device["filesystem"]["uuid"], fsuuid)
        self.assertIsNone(parsed_device["filesystem"]["mount_point"])
        block_device = reload_object(block_device)
        self.assertIsNotNone(block_device.get_effective_filesystem())

    def test_format_formats_block_device_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        fstype = factory.pick_filesystem_type()
        fsuuid = "%s" % uuid.uuid4()
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri, {"op": "format", "fstype": fstype, "uuid": fsuuid}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(parsed_device["filesystem"]["fstype"], fstype)
        self.assertEqual(parsed_device["filesystem"]["uuid"], fsuuid)
        self.assertIsNone(parsed_device["filesystem"]["mount_point"])
        block_device = reload_object(block_device)
        self.assertIsNotNone(block_device.get_effective_filesystem())

    def test_unformat_returns_409_if_not_allocated_or_ready(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_unformat_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_unformat_returns_400_if_not_formatted(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(b"Block device is not formatted.", response.content)

    def test_unformat_returns_400_if_mounted(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device, mount_point="/mnt")
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b"Filesystem is mounted and cannot be unformatted. Unmount the "
            b"filesystem before unformatting the block device.",
            response.content,
        )

    def test_unformat_returns_400_if_in_filesystem_group(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        lvm_filesystem = factory.make_Filesystem(
            block_device=block_device, fstype=FILESYSTEM_TYPE.LVM_PV
        )
        fsgroup = factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
            filesystems=[lvm_filesystem],
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        expected = (
            "Filesystem is part of a %s, and cannot be "
            "unformatted. Remove block device from %s "
            "before unformatting the block device."
            % (fsgroup.get_nice_name(), fsgroup.get_nice_name())
        )
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET), response.content
        )

    def test_unformat_deletes_filesystem_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertIsNone(parsed_device["filesystem"])
        block_device = reload_object(block_device)
        self.assertIsNone(block_device.get_effective_filesystem())

    def test_unformat_deletes_filesystem_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device, acquired=True)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unformat"})

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertIsNone(parsed_device["filesystem"])
        block_device = reload_object(block_device)
        self.assertIsNone(block_device.get_effective_filesystem())

    def test_mount_returns_409_if_not_allocated_or_ready(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "mount"})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_mount_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "mount"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_mount_sets_mount_path_and_params_on_filesystem_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        filesystem = factory.make_Filesystem(block_device=block_device)
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("mount-options")
        uri = get_blockdevice_uri(block_device)
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
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(
            parsed_device["filesystem"].get("mount_point"), mount_point
        )
        self.assertEqual(
            parsed_device["filesystem"].get("mount_options"), mount_options
        )
        fs = reload_object(filesystem)
        self.assertEqual(mount_point, fs.mount_point)
        self.assertEqual(mount_options, fs.mount_options)
        self.assertTrue(fs.is_mounted)

    def test_mount_sets_mount_path_and_params_on_filesystem_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, acquired=True
        )
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("mount-options")
        uri = get_blockdevice_uri(block_device)
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
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(
            parsed_device["filesystem"].get("mount_point"), mount_point
        )
        self.assertEqual(
            parsed_device["filesystem"].get("mount_options"), mount_options
        )
        fs = reload_object(filesystem)
        self.assertEqual(mount_point, fs.mount_point)
        self.assertEqual(mount_options, fs.mount_options)
        self.assertTrue(fs.is_mounted)

    def test_unmount_returns_409_if_not_allocated_or_ready(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[NODE_STATUS.READY, NODE_STATUS.ALLOCATED]
        )
        node = factory.make_Node(status=status, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device, mount_point="/mnt")
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_unmount_returns_403_if_ready_and_not_admin(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device, mount_point="/mnt")
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unmount"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_mount_returns_400_on_missing_mount_point(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "mount"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        parsed_error = json_load_bytes(response.content)
        self.assertEqual(
            {"mount_point": ["This field is required."]}, parsed_error
        )

    def test_unmount_returns_400_if_not_formatted(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unmount"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(b"Block device is not formatted.", response.content)

    def test_unmount_returns_400_if_already_unmounted(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        factory.make_Filesystem(block_device=block_device)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unmount"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(b"Filesystem is already unmounted.", response.content)

    def test_unmount_unmounts_filesystem_as_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        block_device = factory.make_VirtualBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, mount_point="/mnt"
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unmount"})

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        filesystem_json = json_load_bytes(response.content)["filesystem"]
        self.assertIsNone(filesystem_json.get("mount_point", object()))
        self.assertIsNone(filesystem_json.get("mount_options", object()))
        fs = reload_object(filesystem)
        self.assertIsNone(fs.mount_point)
        self.assertIsNone(fs.mount_options)
        self.assertFalse(fs.is_mounted)

    def test_unmount_unmounts_filesystem_as_user(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            block_device=block_device, mount_point="/mnt", acquired=True
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(uri, {"op": "unmount"})

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        filesystem_json = json_load_bytes(response.content)["filesystem"]
        self.assertIsNone(filesystem_json.get("mount_point", object()))
        self.assertIsNone(filesystem_json.get("mount_options", object()))
        fs = reload_object(filesystem)
        self.assertIsNone(fs.mount_point)
        self.assertIsNone(fs.mount_options)
        self.assertFalse(fs.is_mounted)

    def test_update_physical_block_device_as_admin(self):
        """Check update block device with a physical one.

        PUT /api/2.0/nodes/{system_id}/blockdevice/{id}
        """
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            name="myblockdevice",
            size=MIN_BLOCK_DEVICE_SIZE,
            block_size=1024,
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.put(
            uri, {"name": "mynewname", "block_size": 4096}
        )
        block_device = reload_object(block_device)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(parsed_device["id"], block_device.id)
        self.assertEqual("mynewname", parsed_device["name"])
        self.assertEqual(4096, parsed_device["block_size"])

    def test_update_deployed_physical_block_device_as_admin(self):
        """Update deployed physical block device.

        PUT /api/2.0/nodes/{system_id}/blockdevice/{id}
        """
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            name="myblockdevice",
            size=MIN_BLOCK_DEVICE_SIZE,
            block_size=1024,
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.put(
            uri, {"name": "mynewname", "block_size": 4096}
        )
        block_device = reload_object(block_device)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(parsed_device["id"], block_device.id)
        self.assertEqual("mynewname", parsed_device["name"])
        self.assertEqual(1024, parsed_device["block_size"])

    def test_update_virtual_block_device_as_admin(self):
        """Check update block device with a virtual one.

        PUT /api/2.0/nodes/{system_id}/blockdevice/{id}
        """
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY, owner=self.user)
        filesystem_group = factory.make_FilesystemGroup(
            node=node,
            group_type=factory.pick_enum(
                FILESYSTEM_GROUP_TYPE, but_not=[FILESYSTEM_GROUP_TYPE.LVM_VG]
            ),
        )
        block_device = filesystem_group.virtual_device
        uri = get_blockdevice_uri(block_device)
        name = factory.make_name("newname")
        response = self.client.put(uri, {"name": name})
        block_device = reload_object(block_device)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(block_device.id, parsed_device["id"])
        self.assertEqual(name, parsed_device["name"])

    def test_update_physical_block_device_as_normal_user(self):
        """Check update block device with a physical one fails for a normal
        user."""
        node = factory.make_Node(owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(
            node=node,
            name="myblockdevice",
            size=MIN_BLOCK_DEVICE_SIZE,
            block_size=1024,
        )
        uri = get_blockdevice_uri(block_device)
        response = self.client.put(
            uri, {"name": "mynewname", "block_size": 4096}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_virtual_block_device_as_normal_user(self):
        """Check update block device with a virtual one fails for a normal
        user."""
        node = factory.make_Node(owner=self.user)
        newname = factory.make_name("lv")
        block_device = factory.make_VirtualBlockDevice(node=node, name=newname)
        uri = get_blockdevice_uri(block_device)
        response = self.client.put(uri, {"name": newname})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_returns_409_for_non_ready_node(self):
        """Check update block device with a virtual one fails for a normal
        user."""
        self.become_admin()
        node = factory.make_Node(
            status=factory.pick_enum(NODE_STATUS, but_not=[NODE_STATUS.READY])
        )
        newname = factory.make_name("lv")
        block_device = factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.put(uri, {"name": newname})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content
        )

    def test_set_boot_disk_returns_400_for_virtual_device(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY, owner=self.user)
        block_device = factory.make_VirtualBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri,
            {
                "op": "set_boot_disk",
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b"Cannot set a virtual block device as the boot disk.",
            response.content,
        )

    def test_set_boot_disk_returns_403_for_normal_user(self):
        node = factory.make_Node(status=NODE_STATUS.READY, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri,
            {
                "op": "set_boot_disk",
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_set_boot_disk_returns_404_for_block_device_not_on_node(self):
        node = factory.make_Node(owner=self.user)
        block_device = factory.make_PhysicalBlockDevice()
        uri = get_blockdevice_uri(block_device, node=node)
        response = self.client.post(
            uri,
            {
                "op": "set_boot_disk",
            },
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_set_boot_disk_sets_boot_disk_for_admin(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY, owner=self.user)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        uri = get_blockdevice_uri(block_device)
        response = self.client.post(
            uri,
            {
                "op": "set_boot_disk",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        node = reload_object(node)
        self.assertEqual(block_device, node.boot_disk)
