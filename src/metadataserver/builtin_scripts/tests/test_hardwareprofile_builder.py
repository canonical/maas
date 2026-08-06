# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for HardwareProfileBuilder.from_commissioning_output using the same
commissioning fixtures that exercise process_lxd_results.

Tests were adapted from src/metadataserver/builtin_scripts/tests/test_hooks.py.
"""

from copy import deepcopy
import random

from maasserver.testing.commissioning import (
    FakeCommissioningData,
    LXDDisk,
    LXDNetworkCard,
    LXDNetworkPort,
)
from maasserver.testing.factory import factory
from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.tests.test_hooks import (
    make_lxd_output,
    SAMPLE_LXD_RESOURCES_LP1906834,
    SAMPLE_LXD_RESOURCES_NO_NUMA,
)
from provisioningserver.utils.tests.test_lxd import SAMPLE_LXD_RESOURCES

GB = 1000**3
NODE_ID = 1


class TestHardwareProfileBuilderFromSampleLXDResources(MAASTestCase):
    def test_sample_lxd_resources(self):
        output = make_lxd_output(
            resources=deepcopy(SAMPLE_LXD_RESOURCES),
            kernel_architecture="x86_64",
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )
        self.assertEqual(profile.architecture, "amd64/generic")
        self.assertEqual(profile.cpu_cores, 8)
        self.assertEqual(profile.cpu_speed_mhz, 2400)
        self.assertEqual(profile.memory_mb, 15918)
        self.assertEqual(profile.disk_count, 2)
        self.assertEqual(profile.nic_count, 3)
        self.assertEqual(profile.gpu_count, 1)

    def test_sample_lxd_resources_system_info_is_populated(self):
        output = make_lxd_output(resources=deepcopy(SAMPLE_LXD_RESOURCES))
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )
        self.assertIsNotNone(profile.system_vendor)
        self.assertIsNotNone(profile.system_product)

    def test_sample_lxd_resources_storage_grouped_by_type(self):
        output = make_lxd_output(resources=deepcopy(SAMPLE_LXD_RESOURCES))
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )
        groups = {group.disk_type for group in profile.storage}
        self.assertEqual(groups, {"sata", "scsi"})


class TestHardwareProfileBuilderFromRealWorldSamples(MAASTestCase):
    def test_no_numa_rpi4(self):
        output = make_lxd_output(
            resources=deepcopy(SAMPLE_LXD_RESOURCES_NO_NUMA),
            kernel_architecture="aarch64",
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )
        self.assertEqual(profile.architecture, "arm64/generic")
        self.assertEqual(profile.cpu_cores, 4)
        # The socket has no model name, so the speed falls back to the turbo
        # frequency.
        self.assertEqual(profile.cpu_speed_mhz, 1500)
        self.assertEqual(profile.memory_mb, 3791)
        self.assertEqual(profile.disk_count, 2)
        self.assertEqual(profile.nic_count, 2)
        self.assertEqual(profile.gpu_count, 0)

    def test_lp1906834_skips_cdrom_and_zero_sized_disks(self):
        output = make_lxd_output(
            resources=deepcopy(SAMPLE_LXD_RESOURCES_LP1906834),
            kernel_architecture="aarch64",
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )
        self.assertEqual(profile.cpu_cores, 1)
        self.assertEqual(profile.memory_mb, 262144)
        # 2 nvme + 1 sata are modelled; the 0-sized usb disk and the cdrom are
        # skipped.
        self.assertEqual(profile.disk_count, 3)
        self.assertEqual(profile.nic_count, 2)
        self.assertEqual(profile.gpu_count, 0)

    def test_all_samples_parse_without_error(self):
        for resources in (
            SAMPLE_LXD_RESOURCES,
            SAMPLE_LXD_RESOURCES_NO_NUMA,
            SAMPLE_LXD_RESOURCES_LP1906834,
        ):
            output = make_lxd_output(resources=deepcopy(resources))
            HardwareProfileBuilder.from_commissioning_output(output, NODE_ID)


class TestHardwareProfileBuilderFromFakeCommissioningData(MAASTestCase):
    def test_cpu_memory_and_architecture(self):
        data = FakeCommissioningData(
            cores=4, memory=8192, kernel_architecture="x86_64"
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            data.render(), NODE_ID
        )
        self.assertEqual(profile.architecture, "amd64/generic")
        self.assertEqual(profile.cpu_cores, 4)
        self.assertEqual(profile.memory_mb, 8192)

    def test_storage_counts_and_grouping(self):
        data = FakeCommissioningData(
            disks=[
                LXDDisk("sda", size=250 * GB),
                LXDDisk("sdb", size=250 * GB),
                LXDDisk("nvme0n1", size=500 * GB, type="nvme"),
            ]
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            data.render(), NODE_ID
        )
        self.assertEqual(profile.disk_count, 3)
        self.assertEqual(profile.total_storage_bytes, 1000 * GB)
        by_size = sorted(
            (group.disk_type, group.size_bytes, group.count)
            for group in profile.storage
        )
        self.assertEqual(
            by_size,
            [
                ("nvme", 500 * GB, 1),
                ("sata", 250 * GB, 2),
            ],
        )

    def test_network_counts_and_sriov(self):
        data = FakeCommissioningData()
        card = LXDNetworkCard(
            pci_address=data.allocate_pci_address(),
            vendor="Intel",
            product="X710",
        )
        card.ports = []
        data._network_cards.append(card)
        data.create_physical_network(
            card=card,
            port=LXDNetworkPort("eth0", 0, address="aa:bb:cc:dd:ee:01"),
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            data.render(), NODE_ID
        )
        self.assertEqual(profile.nic_count, 1)
        [group] = [
            group for group in profile.network if group.product == "X710"
        ]
        self.assertEqual(group.speed_mbps, 10000)
        self.assertEqual(group.items[0].mac_address, "aa:bb:cc:dd:ee:01")

    def test_skips_ipoib_interfaces(self):
        data = FakeCommissioningData()
        card = data.create_network_card()
        card.ports = []
        data.create_physical_network(
            card=card,
            port=LXDNetworkPort(
                "ibp1",
                0,
                address=(
                    "a0:00:02:20:fe:80:00:00:00:00:00:00"
                    ":e4:1d:2d:03:00:57:5c:e1"
                ),
            ),
        )
        profile = HardwareProfileBuilder.from_commissioning_output(
            data.render(), NODE_ID
        )
        self.assertEqual(profile.nic_count, 0)


class TestHardwareProfileBuilderLunCondensing(MAASTestCase):
    def test_condenses_luns(self):
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        device_path_prefix = f"ccw-0.0.0008-fc-0x{factory.make_hex_string(16)}"
        lun1_model = factory.make_name("lun1_model")
        lun1_size = 1024**3 * random.randint(5, 100)
        lun1_device_path = (
            f"{device_path_prefix}-lun-0x{factory.make_hex_string(16)}"
        )
        lun1_block_size = random.choice([512, 1024, 4096])
        lun1_firmware_version = factory.make_name("lun1_firmware_version")
        lun1_serial = factory.make_name("lun1_serial")
        lun2_model = factory.make_name("lun2_model")
        lun2_size = 1024**3 * random.randint(5, 100)
        lun2_device_path = (
            f"{device_path_prefix}-lun-0x{factory.make_hex_string(16)}"
        )
        lun2_block_size = random.choice([512, 1024, 4096])
        lun2_firmware_version = factory.make_name("lun2_firmware_version")
        lun2_serial = factory.make_name("lun2_serial")
        resources["storage"]["disks"] = [
            {
                "id": "sda",
                "device": "8:0",
                "model": lun1_model,
                "type": "scsi",
                "read_only": False,
                "size": lun1_size,
                "removable": False,
                "numa_node": 0,
                "device_path": lun1_device_path,
                "block_size": lun1_block_size,
                "firmware_version": lun1_firmware_version,
                "rpm": 0,
                "serial": lun1_serial,
                "device_id": "",
                "partitions": [],
            },
            {
                "id": "sdb",
                "device": "8:16",
                "model": lun2_model,
                "type": "scsi",
                "read_only": False,
                "size": lun2_size,
                "removable": False,
                "numa_node": 0,
                "device_path": lun2_device_path,
                "block_size": lun2_block_size,
                "firmware_version": lun2_firmware_version,
                "rpm": 0,
                "serial": lun2_serial,
                "device_id": "",
                "partitions": [],
            },
            {
                "id": "sdc",
                "device": "8:112",
                "model": lun1_model,
                "type": "scsi",
                "read_only": False,
                "size": lun1_size,
                "removable": False,
                "numa_node": 0,
                "device_path": lun1_device_path,
                "block_size": lun1_block_size,
                "firmware_version": lun1_firmware_version,
                "rpm": 0,
                "serial": lun1_serial,
                "device_id": "scsi-LUN1",
                "partitions": [],
            },
            {
                "id": "sdd",
                "device": "8:118",
                "model": lun2_model,
                "type": "scsi",
                "read_only": False,
                "size": lun2_size,
                "removable": False,
                "numa_node": 0,
                "device_path": lun2_device_path,
                "block_size": lun2_block_size,
                "firmware_version": lun2_firmware_version,
                "rpm": 0,
                "serial": lun2_serial,
                "device_id": "scsi-LUN2",
                "partitions": [],
            },
        ]

        output = make_lxd_output(resources=resources)
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )

        self.assertEqual(profile.disk_count, 2)
        [group1] = [
            group for group in profile.storage if group.size_bytes == lun1_size
        ]
        [item1] = group1.items
        self.assertEqual(item1.name, "sda")
        self.assertEqual(item1.model, lun1_model)
        self.assertEqual(item1.serial, lun1_serial)
        self.assertEqual(item1.id_path, "/dev/disk/by-id/scsi-LUN1")
        self.assertEqual(item1.block_size, lun1_block_size)
        self.assertEqual(item1.firmware_version, lun1_firmware_version)

        [group2] = [
            group for group in profile.storage if group.size_bytes == lun2_size
        ]
        [item2] = group2.items
        self.assertEqual(item2.name, "sdb")
        self.assertEqual(item2.model, lun2_model)
        self.assertEqual(item2.serial, lun2_serial)
        self.assertEqual(item2.id_path, "/dev/disk/by-id/scsi-LUN2")
        self.assertEqual(item2.block_size, lun2_block_size)
        self.assertEqual(item2.firmware_version, lun2_firmware_version)

    def test_condenses_luns_jbod(self):
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        expander1 = f"pci-0000:81:00.0-sas-exp0x{factory.make_hex_string(16)}"
        expander2 = f"pci-0000:81:00.0-sas-exp0x{factory.make_hex_string(16)}"
        lun1_model = factory.make_name("lun1_model")
        lun1_size = 1024**3 * random.randint(5, 100)
        lun1_block_size = random.choice([512, 1024, 4096])
        lun1_firmware_version = factory.make_name("lun1_firmware_version")
        lun1_serial = factory.make_name("lun1_serial")
        lun2_model = factory.make_name("lun2_model")
        lun2_size = 1024**3 * random.randint(5, 100)
        lun2_block_size = random.choice([512, 1024, 4096])
        lun2_firmware_version = factory.make_name("lun2_firmware_version")
        lun2_serial = factory.make_name("lun2_serial")
        resources["storage"]["disks"] = [
            {
                "id": "sda",
                "device": "8:0",
                "model": lun1_model,
                "type": "scsi",
                "read_only": False,
                "size": lun1_size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"{expander1}-phy2-lun-0",
                "block_size": lun1_block_size,
                "firmware_version": lun1_firmware_version,
                "rpm": 0,
                "serial": lun1_serial,
                "device_id": "",
                "partitions": [],
            },
            {
                "id": "sdb",
                "device": "8:16",
                "model": lun2_model,
                "type": "scsi",
                "read_only": False,
                "size": lun2_size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"{expander1}-phy5-lun-0",
                "block_size": lun2_block_size,
                "firmware_version": lun2_firmware_version,
                "rpm": 0,
                "serial": lun2_serial,
                "device_id": "",
                "partitions": [],
            },
            {
                "id": "sdc",
                "device": "8:112",
                "model": lun1_model,
                "type": "scsi",
                "read_only": False,
                "size": lun1_size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"{expander2}-phy2-lun-0",
                "block_size": lun1_block_size,
                "firmware_version": lun1_firmware_version,
                "rpm": 0,
                "serial": lun1_serial,
                "device_id": "scsi-LUN1",
                "partitions": [],
            },
            {
                "id": "sdd",
                "device": "8:118",
                "model": lun2_model,
                "type": "scsi",
                "read_only": False,
                "size": lun2_size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"{expander2}-phy5-lun-0",
                "block_size": lun2_block_size,
                "firmware_version": lun2_firmware_version,
                "rpm": 0,
                "serial": lun2_serial,
                "device_id": "scsi-LUN2",
                "partitions": [],
            },
        ]

        output = make_lxd_output(resources=resources)
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )

        self.assertEqual(profile.disk_count, 2)
        [group1] = [
            group for group in profile.storage if group.size_bytes == lun1_size
        ]
        [item1] = group1.items
        self.assertEqual(item1.name, "sda")
        self.assertEqual(item1.model, lun1_model)
        self.assertEqual(item1.serial, lun1_serial)
        self.assertEqual(item1.id_path, "/dev/disk/by-id/scsi-LUN1")
        self.assertEqual(item1.block_size, lun1_block_size)
        self.assertEqual(item1.firmware_version, lun1_firmware_version)

        [group2] = [
            group for group in profile.storage if group.size_bytes == lun2_size
        ]
        [item2] = group2.items
        self.assertEqual(item2.name, "sdb")
        self.assertEqual(item2.model, lun2_model)
        self.assertEqual(item2.serial, lun2_serial)
        self.assertEqual(item2.id_path, "/dev/disk/by-id/scsi-LUN2")
        self.assertEqual(item2.block_size, lun2_block_size)
        self.assertEqual(item2.firmware_version, lun2_firmware_version)

    def test_no_condense_luns_different_serial(self):
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        size = 1024**3 * 10
        resources["storage"]["disks"] = [
            {
                "id": "sda",
                "device": "8:0",
                "model": factory.make_name("model"),
                "type": "scsi",
                "read_only": False,
                "size": size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"pci-0.0.0008-sas-0x{factory.make_hex_string(16)}-lun-123",
                "block_size": 512,
                "firmware_version": factory.make_name("firmware"),
                "rpm": 0,
                "serial": factory.make_name("serial"),
                "device_id": factory.make_name("device_id"),
                "partitions": [],
            },
            {
                "id": "sdb",
                "device": "8:16",
                "model": factory.make_name("model"),
                "type": "scsi",
                "read_only": False,
                "size": size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"pci-0.0.0004-sas-0x{factory.make_hex_string(16)}-lun-123",
                "block_size": 512,
                "firmware_version": factory.make_name("firmware"),
                "rpm": 0,
                "serial": factory.make_name("serial"),
                "device_id": factory.make_name("device_id"),
                "partitions": [],
            },
        ]

        output = make_lxd_output(resources=resources)
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )

        self.assertEqual(profile.disk_count, 2)
        [group] = [
            group for group in profile.storage if group.size_bytes == size
        ]
        self.assertEqual(group.count, 2)
        self.assertEqual({item.name for item in group.items}, {"sda", "sdb"})

    def test_no_condense_luns_empty_serial(self):
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        size = 1024**3 * 10
        resources["storage"]["disks"] = [
            {
                "id": "sda",
                "device": "8:0",
                "model": factory.make_name("model"),
                "type": "scsi",
                "read_only": False,
                "size": size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"pci-0.0.0008-sas-0x{factory.make_hex_string(16)}-lun-123",
                "block_size": 512,
                "firmware_version": factory.make_name("firmware"),
                "rpm": 0,
                "serial": "",
                "device_id": factory.make_name("device_id"),
                "partitions": [],
            },
            {
                "id": "sdb",
                "device": "8:16",
                "model": factory.make_name("model"),
                "type": "scsi",
                "read_only": False,
                "size": size,
                "removable": False,
                "numa_node": 0,
                "device_path": f"pci-0.0.0004-sas-0x{factory.make_hex_string(16)}-lun-123",
                "block_size": 512,
                "firmware_version": factory.make_name("firmware"),
                "rpm": 0,
                "serial": "",
                "device_id": factory.make_name("device_id"),
                "partitions": [],
            },
        ]

        output = make_lxd_output(resources=resources)
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )

        self.assertEqual(profile.disk_count, 2)
        [group] = [
            group for group in profile.storage if group.size_bytes == size
        ]
        self.assertEqual(group.count, 2)
        self.assertEqual({item.name for item in group.items}, {"sda", "sdb"})

    def test_no_condense_luns_no_serial(self):
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        resources["storage"]["disks"] = [
            {
                "id": "sde",
                "device": "8:64",
                "model": "IPR-0   6DC90500",
                "type": "scsi",
                "read_only": False,
                "size": 283794997248,
                "removable": False,
                "numa_node": 0,
                "device_path": "pci-0001:08:00.0-scsi-0:2:4:0",
                "block_size": 4096,
                "rpm": 1,
                "serial": "IBM_IPR-0_6DC90500000000A0",
                "device_id": "scsi-1IBM_IPR-0_6DC90500000000A0",
                "partitions": [],
            },
            {
                "id": "sr9",
                "device": "11:0",
                "model": "RMBO0140532",
                "type": "cdrom",
                "read_only": False,
                "size": 0,
                "removable": True,
                "numa_node": 0,
                "device_path": "pci-0001:08:00.0-scsi-0:0:7:0",
                "block_size": 0,
                "firmware_version": "RA64",
                "rpm": 1,
                "device_id": "",
                "partitions": [],
            },
        ]

        output = make_lxd_output(resources=resources)
        profile = HardwareProfileBuilder.from_commissioning_output(
            output, NODE_ID
        )

        # sr9 is not included because it's a cdrom
        self.assertEqual(profile.disk_count, 1)
        [group] = profile.storage
        [item] = group.items
        self.assertEqual(item.name, "sde")
