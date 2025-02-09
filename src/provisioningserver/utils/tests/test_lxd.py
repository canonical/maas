# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for lxd utilities."""

from maastesting.testcase import MAASTestCase
from provisioningserver.utils.lxd import (
    lxd_cpu_speed,
    NUMANode,
    parse_lxd_cpuinfo,
    parse_lxd_networks,
)

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

SAMPLE_LXD_NETWORKS = {
    "lo": {
        "addresses": [
            {
                "family": "inet",
                "address": "127.0.0.1",
                "netmask": "8",
                "scope": "local",
            },
            {
                "family": "inet6",
                "address": "::1",
                "netmask": "128",
                "scope": "local",
            },
        ],
        "hwaddr": "",
        "state": "up",
        "type": "loopback",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "eth0": {
        "addresses": [
            {
                "family": "inet",
                "address": "192.168.0.3",
                "netmask": "24",
                "scope": "global",
            },
            {
                "family": "inet6",
                "address": "fe80::3e97:efe:fe0e:56dc",
                "netmask": "64",
                "scope": "link",
            },
            {
                "family": "inet6",
                "address": "2001:db8:a::123",
                "netmask": "64",
                "scope": "global",
            },
        ],
        "hwaddr": "00:00:00:00:00:01",
        "state": "up",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "eth1": {
        "addresses": [
            {
                "family": "inet",
                "address": "172.17.42.1",
                "netmask": "16",
                "scope": "global",
            },
        ],
        "hwaddr": "00:00:00:00:00:02",
        "state": "down",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "eth2": {
        "addresses": [
            {
                "family": "inet",
                "address": "172.17.12.1",
                "netmask": "16",
                "scope": "global",
            },
        ],
        "hwaddr": "00:00:00:00:00:03",
        "state": "down",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
}


class TestLXDUtils(MAASTestCase):
    def test_lxd_cpu_speed(self):
        self.assertEqual(2400, lxd_cpu_speed(SAMPLE_LXD_RESOURCES))


class TestParseLXDCPUInfo(MAASTestCase):
    def test_cpuinfo(self):
        cpu_count, cpu_speed, cpu_model, numa_nodes = parse_lxd_cpuinfo(
            SAMPLE_LXD_RESOURCES
        )
        self.assertEqual(cpu_count, 8)
        self.assertEqual(cpu_speed, 2400)
        self.assertEqual(cpu_model, "Intel(R) Core(TM) i7-4700MQ CPU")
        self.assertEqual(
            numa_nodes,
            {
                0: NUMANode(memory=0, cores=[0, 1, 2, 3], hugepages=0),
                1: NUMANode(memory=0, cores=[4, 5, 6, 7], hugepages=0),
            },
        )


class TestParseLXDNetworks(MAASTestCase):
    def test_networks(self):
        networks = parse_lxd_networks(SAMPLE_LXD_NETWORKS)
        self.assertEqual(
            networks,
            {
                "eth0": {
                    "type": "broadcast",
                    "enabled": True,
                    "addresses": ["192.168.0.3/24", "2001:db8:a::123/64"],
                    "mac": "00:00:00:00:00:01",
                    "parents": [],
                },
                "eth1": {
                    "type": "broadcast",
                    "enabled": False,
                    "addresses": ["172.17.42.1/16"],
                    "mac": "00:00:00:00:00:02",
                    "parents": [],
                },
                "eth2": {
                    "type": "broadcast",
                    "enabled": False,
                    "addresses": ["172.17.12.1/16"],
                    "mac": "00:00:00:00:00:03",
                    "parents": [],
                },
                "lo": {
                    "type": "loopback",
                    "enabled": True,
                    "addresses": ["127.0.0.1/8", "::1/128"],
                    "mac": "",
                    "parents": [],
                },
            },
        )

    def test_networks_vlan(self):
        network_details = {
            "vlan100": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": {
                    "lower_device": "eth0",
                    "vid": 100,
                },
            },
        }
        networks = parse_lxd_networks(network_details)
        self.assertEqual(
            networks,
            {
                "vlan100": {
                    "type": "vlan",
                    "enabled": True,
                    "addresses": [],
                    "mac": "00:00:00:00:00:01",
                    "parents": ["eth0"],
                    "vid": 100,
                },
            },
        )

    def test_networks_bond(self):
        network_details = {
            "bond0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": {
                    "lower_devices": ["eth0", "eth1"],
                },
                "bridge": None,
                "vlan": None,
            },
        }
        networks = parse_lxd_networks(network_details)
        self.assertEqual(
            networks,
            {
                "bond0": {
                    "type": "bond",
                    "enabled": True,
                    "addresses": [],
                    "mac": "00:00:00:00:00:01",
                    "parents": ["eth0", "eth1"],
                },
            },
        )

    def test_networks_bridge(self):
        network_details = {
            "br0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": {
                    "upper_devices": ["eth0", "eth1"],
                },
                "vlan": None,
            },
        }
        networks = parse_lxd_networks(network_details)
        self.assertEqual(
            networks,
            {
                "br0": {
                    "type": "bridge",
                    "enabled": True,
                    "addresses": [],
                    "mac": "00:00:00:00:00:01",
                    "parents": ["eth0", "eth1"],
                },
            },
        )

    def test_networks_missing_vlan_key(self):
        network_details = {
            "if0": {
                "addresses": [],
                "hwaddr": "00:00:00:00:00:01",
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
            },
        }
        networks = parse_lxd_networks(network_details)
        self.assertEqual(
            networks,
            {
                "if0": {
                    "type": "broadcast",
                    "enabled": True,
                    "addresses": [],
                    "mac": "00:00:00:00:00:01",
                    "parents": [],
                },
            },
        )
