# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for lxd utilities."""


from maastesting.testcase import MAASTestCase
from provisioningserver.utils.lxd import lxd_cpu_speed

SAMPLE_LXD_RESOURCES = {
    "cpu": {
        "architecture": "x86_64",
        "sockets": [
            {
                "name": "Intel(R) Core(TM) i7-4700MQ CPU @ 2.40GHz",
                "vendor": "GenuineIntel",
                "socket": 0,
                "cache": [
                    {"level": 1, "type": "Data", "size": 32768},
                    {"level": 1, "type": "Instruction", "size": 32768},
                    {"level": 2, "type": "Unified", "size": 262144},
                    {"level": 3, "type": "Unified", "size": 6291456},
                ],
                "cores": [
                    {
                        "core": 0,
                        "threads": [
                            {
                                "id": 0,
                                "thread": 0,
                                "online": True,
                                "numa_node": 0,
                            },
                            {
                                "id": 1,
                                "thread": 1,
                                "online": True,
                                "numa_node": 0,
                            },
                        ],
                        "frequency": 3247,
                    },
                    {
                        "core": 1,
                        "threads": [
                            {
                                "id": 2,
                                "thread": 0,
                                "online": True,
                                "numa_node": 0,
                            },
                            {
                                "id": 3,
                                "thread": 1,
                                "online": True,
                                "numa_node": 0,
                            },
                        ],
                        "frequency": 3192,
                    },
                    {
                        "core": 2,
                        "threads": [
                            {
                                "id": 4,
                                "thread": 0,
                                "online": True,
                                "numa_node": 1,
                            },
                            {
                                "id": 5,
                                "thread": 1,
                                "online": True,
                                "numa_node": 1,
                            },
                        ],
                        "frequency": 3241,
                    },
                    {
                        "core": 3,
                        "threads": [
                            {
                                "id": 6,
                                "thread": 0,
                                "online": True,
                                "numa_node": 1,
                            },
                            {
                                "id": 7,
                                "thread": 1,
                                "online": True,
                                "numa_node": 1,
                            },
                        ],
                        "frequency": 3247,
                    },
                ],
                "frequency": 3231,
                "frequency_minimum": 800,
                "frequency_turbo": 3400,
            }
        ],
        "total": 8,
    },
    "memory": {
        "nodes": [
            {
                "numa_node": 0,
                "hugepages_used": 0,
                "hugepages_total": 0,
                "used": 6058246144,
                "total": 8345759744,
            },
            {
                "numa_node": 1,
                "hugepages_used": 0,
                "hugepages_total": 0,
                "used": 6058246144,
                "total": 8345759744,
            },
        ],
        "hugepages_total": 0,
        "hugepages_used": 0,
        "hugepages_size": 2097152,
        "used": 12116492288,
        "total": 16691519488,
    },
    "gpu": {
        "cards": [
            {
                "driver": "i915",
                "driver_version": "4.15.0-58-generic",
                "drm": {
                    "id": 0,
                    "card_name": "card0",
                    "card_device": "226:0",
                    "control_name": "controlD64",
                    "control_device": "226:0",
                    "render_name": "renderD128",
                    "render_device": "226:128",
                },
                "numa_node": 0,
                "pci_address": "0000:00:02.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": (
                    "4th Gen Core Processor Integrated Graphics Controller"
                ),
                "product_id": "0416",
            }
        ],
        "total": 1,
    },
    "network": {
        "cards": [
            {
                "driver": "e1000e",
                "driver_version": "3.2.6-k",
                "ports": [
                    {
                        "id": "eth0",
                        "address": "00:00:00:00:00:01",
                        "port": 0,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "10baseT/Half",
                            "10baseT/Full",
                            "100baseT/Half",
                            "100baseT/Full",
                            "1000baseT/Full",
                        ],
                        "supported_ports": ["twisted pair"],
                        "port_type": "twisted pair",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": True,
                        "link_speed": 1000,
                    }
                ],
                "numa_node": 0,
                "pci_address": "0000:00:19.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "Ethernet Connection I217-LM",
                "product_id": "153a",
                "firmware_version": "1.2.3.4",
                "sriov": {"current_vfs": 0, "maximum_vfs": 8, "vfs": []},
            },
            {
                "driver": "e1000e",
                "driver_version": "3.2.6-k",
                "ports": [
                    {
                        "id": "eth1",
                        "address": "00:00:00:00:00:02",
                        "port": 0,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "10baseT/Half",
                            "10baseT/Full",
                            "100baseT/Half",
                            "100baseT/Full",
                            "1000baseT/Full",
                        ],
                        "supported_ports": ["twisted pair"],
                        "port_type": "twisted pair",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": False,
                    }
                ],
                "numa_node": 1,
                "pci_address": "0000:00:19.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "Ethernet Connection I217-LM",
                "product_id": "153a",
            },
            {
                "driver": "e1000e",
                "driver_version": "3.2.6-k",
                "ports": [
                    {
                        "id": "eth2",
                        "address": "00:00:00:00:00:03",
                        "port": 0,
                        "protocol": "ethernet",
                        "auto_negotiation": False,
                        "link_detected": True,
                    }
                ],
                "numa_node": 0,
                "pci_address": "0000:04:00.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "Wireless 7260",
                "product_id": "08b2",
            },
        ],
        "total": 3,
    },
    "storage": {
        "disks": [
            {
                "id": "sda",
                "device": "8:0",
                "model": "Crucial_CT512M55",
                "type": "sata",
                "read_only": False,
                "size": 512110190592,
                "removable": False,
                "numa_node": 0,
                "device_path": "pci-0000:00:1f.2-ata-1",
                "device_id": "wwn-0x12345",
                "block_size": 4096,
                "rpm": 0,
                "firmware_version": "MU01",
                "serial": "14060968BCD8",
                "partitions": [
                    {
                        "id": "sda1",
                        "device": "8:1",
                        "read_only": False,
                        "size": 536870912,
                        "partition": 1,
                    },
                    {
                        "id": "sda2",
                        "device": "8:2",
                        "read_only": False,
                        "size": 511705088,
                        "partition": 2,
                    },
                    {
                        "id": "sda3",
                        "device": "8:3",
                        "read_only": False,
                        "size": 511060213760,
                        "partition": 3,
                    },
                ],
            },
            {
                # For testing purposes...
                # No device_path, rpm > 0, removable
                "id": "sdb",
                "device": "8:16",
                "model": "WDC WD60EFRX-68M",
                "type": "scsi",
                "read_only": False,
                "size": 6001175126016,
                "block_size": 4096,
                "removable": True,
                "rpm": 5400,
                "numa_node": 1,
                "firmware_version": "MU01",
                "serial": "14060968BCD8",
                "partitions": [
                    {
                        "id": "sdb1",
                        "device": "8:17",
                        "read_only": False,
                        "size": 6001165074432,
                        "partition": 1,
                    },
                    {
                        "id": "sdb9",
                        "device": "8:25",
                        "read_only": False,
                        "size": 8388608,
                        "partition": 9,
                    },
                ],
            },
        ],
        "total": 7,
    },
}


class TestLXDUtils(MAASTestCase):
    def test_lxd_cpu_speed(self):
        self.assertEquals(2400, lxd_cpu_speed(SAMPLE_LXD_RESOURCES))
