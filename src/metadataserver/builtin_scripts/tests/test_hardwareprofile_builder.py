# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for HardwareProfileBuilder.from_commissioning_output using the same
commissioning fixtures that exercise process_lxd_results.
"""

from copy import deepcopy

from maasserver.testing.commissioning import (
    FakeCommissioningData,
    LXDDisk,
    LXDNetworkCard,
    LXDNetworkPort,
)
from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.tests.test_hooks import (
    make_lxd_output,
    SAMPLE_LXD_RESOURCES_LP1906834,
    SAMPLE_LXD_RESOURCES_NO_NUMA,
)
from provisioningserver.utils.tests.test_lxd import SAMPLE_LXD_RESOURCES

GB = 1000**3


def build(output, node_id=1):
    return HardwareProfileBuilder.from_commissioning_output(
        output, node_id
    ).populated_fields()


class TestHardwareProfileBuilderFromSampleLXDResources(MAASTestCase):
    def test_sample_lxd_resources(self):
        output = make_lxd_output(
            resources=deepcopy(SAMPLE_LXD_RESOURCES),
            kernel_architecture="x86_64",
        )
        fields = build(output)
        self.assertEqual(fields["architecture"], "amd64/generic")
        self.assertEqual(fields["cpu_cores"], 8)
        self.assertEqual(fields["cpu_speed_mhz"], 2400)
        self.assertEqual(fields["memory_mb"], 15918)
        self.assertEqual(fields["disk_count"], 2)
        self.assertEqual(fields["nic_count"], 3)
        self.assertEqual(fields["gpu_count"], 1)

    def test_sample_lxd_resources_system_info_is_populated(self):
        output = make_lxd_output(resources=deepcopy(SAMPLE_LXD_RESOURCES))
        fields = build(output)
        self.assertIsNotNone(fields["system_vendor"])
        self.assertIsNotNone(fields["system_product"])

    def test_sample_lxd_resources_storage_grouped_by_type(self):
        output = make_lxd_output(resources=deepcopy(SAMPLE_LXD_RESOURCES))
        fields = build(output)
        groups = {group["disk_type"] for group in fields["storage"]}
        self.assertEqual(groups, {"sata", "scsi"})


class TestHardwareProfileBuilderFromRealWorldSamples(MAASTestCase):
    def test_no_numa_rpi4(self):
        output = make_lxd_output(
            resources=deepcopy(SAMPLE_LXD_RESOURCES_NO_NUMA),
            kernel_architecture="aarch64",
        )
        fields = build(output)
        self.assertEqual(fields["architecture"], "arm64/generic")
        self.assertEqual(fields["cpu_cores"], 4)
        # The socket has no model name, so the speed falls back to the turbo
        # frequency.
        self.assertEqual(fields["cpu_speed_mhz"], 1500)
        self.assertEqual(fields["memory_mb"], 3791)
        self.assertEqual(fields["disk_count"], 2)
        self.assertEqual(fields["nic_count"], 2)
        self.assertEqual(fields["gpu_count"], 0)

    def test_lp1906834_skips_cdrom_and_zero_sized_disks(self):
        output = make_lxd_output(
            resources=deepcopy(SAMPLE_LXD_RESOURCES_LP1906834),
            kernel_architecture="aarch64",
        )
        fields = build(output)
        self.assertEqual(fields["cpu_cores"], 1)
        self.assertEqual(fields["memory_mb"], 262144)
        # 2 nvme + 1 sata are modelled; the 0-sized usb disk and the cdrom are
        # skipped.
        self.assertEqual(fields["disk_count"], 3)
        self.assertEqual(fields["nic_count"], 2)
        self.assertEqual(fields["gpu_count"], 0)

    def test_all_samples_parse_without_error(self):
        for resources in (
            SAMPLE_LXD_RESOURCES,
            SAMPLE_LXD_RESOURCES_NO_NUMA,
            SAMPLE_LXD_RESOURCES_LP1906834,
        ):
            output = make_lxd_output(resources=deepcopy(resources))
            self.assertIsInstance(build(output)["hardware_fingerprint"], str)


class TestHardwareProfileBuilderFromFakeCommissioningData(MAASTestCase):
    def test_cpu_memory_and_architecture(self):
        data = FakeCommissioningData(
            cores=4, memory=8192, kernel_architecture="x86_64"
        )
        fields = build(data.render())
        self.assertEqual(fields["architecture"], "amd64/generic")
        self.assertEqual(fields["cpu_cores"], 4)
        self.assertEqual(fields["memory_mb"], 8192)

    def test_storage_counts_and_grouping(self):
        data = FakeCommissioningData(
            disks=[
                LXDDisk("sda", size=250 * GB),
                LXDDisk("sdb", size=250 * GB),
                LXDDisk("nvme0n1", size=500 * GB, type="nvme"),
            ]
        )
        fields = build(data.render())
        self.assertEqual(fields["disk_count"], 3)
        self.assertEqual(fields["total_storage_bytes"], 1000 * GB)
        by_size = sorted(
            (group["disk_type"], group["size_bytes"], group["count"])
            for group in fields["storage"]
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
        fields = build(data.render())
        self.assertEqual(fields["nic_count"], 1)
        [group] = [
            group for group in fields["network"] if group["product"] == "X710"
        ]
        self.assertEqual(group["speed_mbps"], 10000)
        self.assertEqual(group["items"][0]["mac_address"], "aa:bb:cc:dd:ee:01")

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
        fields = build(data.render())
        self.assertEqual(fields["nic_count"], 0)
