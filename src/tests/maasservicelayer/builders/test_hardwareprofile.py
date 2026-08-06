# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder

SAMPLE_RESOURCES = {
    "cpu": {
        "architecture": "x86_64",
        "sockets": [
            {
                "name": "Intel(R) Core(TM) i7-4700MQ CPU @ 2.40GHz",
                "vendor": "GenuineIntel",
                "socket": 0,
                "cores": [
                    {
                        "core": 0,
                        "threads": [
                            {"id": 0, "thread": 0, "numa_node": 0},
                        ],
                        "frequency": 3247,
                    },
                ],
                "frequency": 3231,
                "frequency_turbo": 3400,
            }
        ],
        "total": 8,
    },
    "memory": {"total": 16691519488},
    "gpu": {
        "cards": [
            {
                "driver": "i915",
                "drm": {"id": 0, "card_name": "card0"},
                "numa_node": 0,
                "pci_address": "0000:00:02.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "HD Graphics",
                "product_id": "0416",
            }
        ],
        "total": 1,
    },
    "network": {
        "cards": [
            {
                "ports": [
                    {
                        "id": "eth0",
                        "address": "00:00:00:00:00:01",
                        "supported_modes": ["100baseT/Full", "1000baseT/Full"],
                        "link_speed": 1000,
                    }
                ],
                "numa_node": 0,
                "pci_address": "0000:00:19.0",
                "vendor": "Intel Corporation",
                "product": "Ethernet Connection I217-LM",
                "sriov": {"current_vfs": 0, "maximum_vfs": 8, "vfs": None},
            }
        ],
        "total": 1,
    },
    "storage": {
        "disks": [
            {
                "id": "sda",
                "type": "sata",
                "read_only": False,
                "size": 512110190592,
                "block_size": 4096,
                "numa_node": 0,
                "device_id": "wwn-0x12345",
                "serial": "14060968BCD8",
                "firmware_version": "MU01",
                "model": "Crucial_CT512M55",
            },
            {
                "id": "sr0",
                "type": "cdrom",
                "read_only": True,
                "size": 0,
                "numa_node": 0,
            },
        ],
        "total": 2,
    },
    "system": {"vendor": "LENOVO", "product": "20HRCTO1WW"},
}


def make_output(resources=None, **extra):
    output = {
        "api_version": "1.0",
        "api_extensions": ["resources"],
        "environment": {
            "kernel_architecture": "x86_64",
            "os_name": "ubuntu",
            "os_version": "22.04",
        },
        "resources": resources if resources is not None else SAMPLE_RESOURCES,
        "networks": {},
    }
    output.update(extra)
    return output


def build_fields(resources=None, node_id=1, **extra):
    builder = HardwareProfileBuilder.from_commissioning_output(
        make_output(resources, **extra), node_id
    )
    return builder.populated_fields()


class TestHardwareProfileBuilderFromCommissioningOutput:
    def test_maps_cpu_memory_and_architecture(self):
        fields = build_fields()
        assert fields["architecture"] == "amd64/generic"
        assert fields["cpu_cores"] == 8
        assert fields["cpu_speed_mhz"] == 2400
        assert fields["memory_mb"] == 15918

    def test_sets_node_id(self):
        assert build_fields(node_id=42)["node_id"] == 42

    def test_maps_system_vendor_and_product(self):
        fields = build_fields()
        assert fields["system_vendor"] == "LENOVO"
        assert fields["system_product"] == "20HRCTO1WW"

    def test_groups_storage_and_skips_cdrom(self):
        fields = build_fields()
        assert fields["disk_count"] == 1
        assert fields["total_storage_bytes"] == 512110190592
        [group] = fields["storage"]
        assert group["disk_type"] == "sata"
        assert group["size_bytes"] == 512110190592
        assert group["items"][0]["id_path"] == "/dev/disk/by-id/wwn-0x12345"

    def test_condenses_multipath_luns(self):
        def path(disk_id, expander, device_id):
            return {
                "id": disk_id,
                "type": "scsi",
                "read_only": False,
                "size": 500_000_000_000,
                "block_size": 512,
                "numa_node": 0,
                "serial": "SN123",
                "device_id": device_id,
                "device_path": f"pci-0000:81:00.0-sas-{expander}-phy2-lun-0",
            }

        resources = {
            **SAMPLE_RESOURCES,
            "storage": {
                "disks": [
                    path("sda", "exp0x500", ""),
                    path("sdb", "exp0x501", "wwn-0xLUN1"),
                ],
                "total": 2,
            },
        }
        fields = build_fields(resources)
        assert fields["disk_count"] == 1
        assert fields["total_storage_bytes"] == 500_000_000_000
        [group] = fields["storage"]
        [item] = group["items"]
        assert item["name"] == "sda"
        # The by-id link is only reported on the second path.
        assert item["id_path"] == "/dev/disk/by-id/wwn-0xLUN1"

    def test_keeps_luns_with_different_serials(self):
        def lun(disk_id, serial):
            return {
                "id": disk_id,
                "type": "scsi",
                "read_only": False,
                "size": 500_000_000_000,
                "block_size": 512,
                "numa_node": 0,
                "serial": serial,
                "device_path": "pci-0000:81:00.0-sas-exp0x500-phy2-lun-0",
            }

        resources = {
            **SAMPLE_RESOURCES,
            "storage": {
                "disks": [lun("sda", "SN123"), lun("sdb", "SN456")],
                "total": 2,
            },
        }
        assert build_fields(resources)["disk_count"] == 2

    def test_skips_virtual_bcache_holders(self):
        resources = {
            **SAMPLE_RESOURCES,
            "storage": {
                "disks": [
                    *SAMPLE_RESOURCES["storage"]["disks"],
                    {
                        "id": "bcache0",
                        "type": "scsi",
                        "read_only": False,
                        "size": 512110190592,
                        "block_size": 512,
                        "numa_node": 0,
                    },
                ],
                "total": 3,
            },
        }
        fields = build_fields(resources)
        assert fields["disk_count"] == 1
        assert fields["total_storage_bytes"] == 512110190592

    def test_groups_storage_by_type_and_size(self):
        resources = {
            **SAMPLE_RESOURCES,
            "storage": {
                "disks": [
                    {
                        "id": "sda",
                        "type": "sata",
                        "read_only": False,
                        "size": 1_000_000_000,
                        "block_size": 512,
                        "numa_node": 0,
                    },
                    {
                        "id": "sdb",
                        "type": "sata",
                        "read_only": False,
                        "size": 1_000_000_000,
                        "block_size": 512,
                        "numa_node": 0,
                    },
                    {
                        "id": "sdc",
                        "type": "sata",
                        "read_only": False,
                        "size": 2_000_000_000,
                        "block_size": 512,
                        "numa_node": 0,
                    },
                ],
                "total": 3,
            },
        }
        fields = build_fields(resources)
        assert fields["disk_count"] == 3
        # Same type but different size stay in separate groups; group size is
        # the size of a single disk.
        groups = sorted(fields["storage"], key=lambda g: g["size_bytes"])
        assert [(g["size_bytes"], g["count"]) for g in groups] == [
            (1_000_000_000, 2),
            (2_000_000_000, 1),
        ]
        assert fields["total_storage_bytes"] == 4_000_000_000

    def test_groups_network_with_sriov_and_speed(self):
        fields = build_fields()
        assert fields["nic_count"] == 1
        [group] = fields["network"]
        assert group["speed_mbps"] == 1000
        assert group["items"][0]["sriov_max_vf"] == 8
        assert group["items"][0]["mac_address"] == "00:00:00:00:00:01"

    def test_groups_accelerators(self):
        fields = build_fields()
        assert fields["gpu_count"] == 1
        [group] = fields["accelerators"]
        assert group["vendor"] == "Intel Corporation"
        assert group["items"][0]["pci_address"] == "0000:00:02.0"

    def test_gpu_count_matches_accelerators(self):
        resources = {
            **SAMPLE_RESOURCES,
            "gpu": {
                "cards": [
                    *SAMPLE_RESOURCES["gpu"]["cards"],
                    {
                        "drm": {"id": 1, "card_name": "card1"},
                        "mdev": {"nvidia-256": {"name": "GRID A100-1-5C"}},
                        "numa_node": 0,
                        "pci_address": "0000:81:00.0",
                        "vendor": "NVIDIA Corporation",
                        "vendor_id": "10de",
                        "product": "GA100",
                        "product_id": "20b0",
                    },
                ],
                "total": 2,
            },
        }
        fields = build_fields(resources)
        assert fields["gpu_count"] == 2
        assert sum(g["count"] for g in fields["accelerators"]) == 2

    def test_platform_overrides_architecture_subarch(self):
        fields = build_fields(**{"machine-extra": {"platform": "raspi"}})
        assert fields["architecture"] == "amd64/raspi"

    def test_skips_ipoib_mac_addresses(self):
        resources = {
            **SAMPLE_RESOURCES,
            "network": {
                "cards": [
                    {
                        "ports": [
                            {
                                "id": " ibp1",
                                "address": (
                                    "a0:00:02:20:fe:80:00:00:00:00:00:00"
                                    ":e4:1d:2d:03:00:57:5c:e1"
                                ),
                            }
                        ],
                        "numa_node": 0,
                    }
                ],
                "total": 1,
            },
        }
        assert build_fields(resources)["nic_count"] == 0

    @pytest.mark.parametrize(
        "sockets,expected_speed",
        [
            ([{"name": "CPU", "frequency_turbo": 3400}], 3400),
            ([{"name": "CPU", "frequency": 3231}], 3200),
        ],
    )
    def test_cpu_speed_fallbacks(self, sockets, expected_speed):
        resources = {
            **SAMPLE_RESOURCES,
            "cpu": {"sockets": sockets, "total": 4},
        }
        fields = build_fields(resources)
        assert fields["cpu_speed_mhz"] == expected_speed
