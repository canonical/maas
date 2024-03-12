# Copyright 2012-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from copy import deepcopy
import json
import random

from distro_info import UbuntuDistroInfo
from django.db.models import Q
from fixtures import FakeLogger
from netaddr import IPNetwork
from testtools.matchers import Equals, MatchesStructure

from maasserver.enum import (
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_DEVICE_BUS,
    NODE_METADATA,
    NODE_STATUS,
    PARTITION_TABLE_TYPE,
)
from maasserver.models import (
    NodeMetadata,
    NUMANode,
    PhysicalInterface,
    ScriptSet,
    Tag,
    VLAN,
)
from maasserver.models import Config, Event, EventType, Interface, Node
from maasserver.models import node as node_module
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.storage_custom import ConfigError
from maasserver.storage_layouts import get_applied_storage_layout_for_node
from maasserver.testing.commissioning import (
    FakeCommissioningData,
    LXDNetworkCard,
    LXDPCIDeviceVPD,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import MockNotCalled
from maastesting.testcase import MAASTestCase
import metadataserver.builtin_scripts.hooks as hooks_module
from metadataserver.builtin_scripts.hooks import (
    _hardware_sync_block_device_notify,
    _hardware_sync_cpu_notify,
    _hardware_sync_memory_notify,
    _hardware_sync_node_device_notify,
    _hardware_sync_notify,
    _update_node_physical_block_devices,
    add_switch_vendor_model_tags,
    create_metadata_by_modalias,
    detect_switch_vendor_model,
    determine_hardware_matches,
    filter_modaliases,
    get_dmi_data,
    NODE_INFO_SCRIPTS,
    parse_interfaces,
    process_lxd_results,
    retag_node_for_hardware_by_modalias,
    update_node_fruid_metadata,
    update_node_network_information,
)
from metadataserver.enum import (
    HARDWARE_SYNC_ACTIONS,
    HARDWARE_TYPE,
    SCRIPT_TYPE,
)
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES
from provisioningserver.refresh.node_info_scripts import (
    KERNEL_CMDLINE_OUTPUT_NAME,
)
from provisioningserver.utils.tests.test_lxd import (
    SAMPLE_LXD_NETWORKS,
    SAMPLE_LXD_RESOURCES,
)

lldp_output_template = """
<?xml version="1.0" encoding="UTF-8"?>
<lldp label="LLDP neighbors">
%s
</lldp>
"""


lldp_output_interface_template = """
<interface label="Interface" name="eth1" via="LLDP">
  <chassis label="Chassis">
    <id label="ChassisID" type="mac">%s</id>
    <name label="SysName">switch-name</name>
    <descr label="SysDescr">HDFD5BG7J</descr>
    <mgmt-ip label="MgmtIP">192.168.9.9</mgmt-ip>
    <capability label="Capability" type="Bridge" enabled="on"/>
    <capability label="Capability" type="Router" enabled="off"/>
  </chassis>
</interface>
"""


def make_lxd_system_info(virt_type=None, uuid=None):
    if not virt_type:
        virt_type = random.choice(["physical", "container", "virtual-machine"])
    if uuid is None:
        uuid = factory.make_UUID()
    return {
        "uuid": uuid,
        "vendor": factory.make_name("system_vendor"),
        "product": factory.make_name("system_product"),
        "family": factory.make_name("system_family"),
        "version": factory.make_name("system_version"),
        "sku": factory.make_name("system_sku"),
        "serial": factory.make_name("system_serial"),
        "type": virt_type,
        "firmware": {
            "vendor": factory.make_name("mainboard_firmware_vendor"),
            "date": "04/20/2020",
            "version": factory.make_name("mainboard_firmware_version"),
        },
        "chassis": {
            "vendor": factory.make_name("chassis_vendor"),
            "type": factory.make_name("chassis_type"),
            "serial": factory.make_name("chassis_serial"),
            "version": factory.make_name("chassis_version"),
        },
        "motherboard": {
            "vendor": factory.make_name("motherboard_vendor"),
            "product": factory.make_name("motherboard_product"),
            "serial": factory.make_name("motherboard_serial"),
            "version": factory.make_name("motherboard_version"),
        },
    }


# This is sample output from a rpi4
SAMPLE_LXD_RESOURCES_NO_NUMA = {
    "cpu": {
        "architecture": "aarch64",
        "sockets": [
            {
                "socket": 0,
                "cores": [
                    {
                        "core": 0,
                        "threads": [
                            {
                                "id": 0,
                                "thread": 0,
                                "online": True,
                                "numa_node": 0,
                            }
                        ],
                        "frequency": 1500,
                    },
                    {
                        "core": 1,
                        "threads": [
                            {
                                "id": 1,
                                "thread": 0,
                                "online": True,
                                "numa_node": 0,
                            }
                        ],
                        "frequency": 1500,
                    },
                    {
                        "core": 2,
                        "threads": [
                            {
                                "id": 2,
                                "thread": 0,
                                "online": True,
                                "numa_node": 0,
                            }
                        ],
                        "frequency": 1500,
                    },
                    {
                        "core": 3,
                        "threads": [
                            {
                                "id": 3,
                                "thread": 0,
                                "online": True,
                                "numa_node": 0,
                            }
                        ],
                        "frequency": 1500,
                    },
                ],
                "frequency": 1500,
                "frequency_minimum": 600,
                "frequency_turbo": 1500,
            }
        ],
        "total": 4,
    },
    "memory": {
        "hugepages_total": 0,
        "hugepages_used": 0,
        "hugepages_size": 0,
        "used": 2179518464,
        "total": 3975593984,
    },
    "gpu": {"cards": [], "total": 0},
    "network": {
        "cards": [
            {
                "driver": "bcmgenet",
                "driver_version": "5.3.0-1019-raspi2",
                "ports": [
                    {
                        "id": "eth0",
                        "address": "dc:a6:32:52:b2:6c",
                        "port": 0,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "10baseT/Half",
                            "10baseT/Full",
                            "100baseT/Half",
                            "100baseT/Full",
                            "1000baseT/Half",
                            "1000baseT/Full",
                        ],
                        "supported_ports": [
                            "twisted pair",
                            "media-independent",
                        ],
                        "port_type": "media-independent",
                        "transceiver_type": "external",
                        "auto_negotiation": True,
                        "link_detected": True,
                        "link_speed": 1000,
                        "link_duplex": "full",
                    }
                ],
                "numa_node": 0,
            },
            {
                "driver": "brcmfmac",
                "driver_version": "5.3.0-1019-raspi2",
                "ports": [
                    {
                        "id": "wlan0",
                        "address": "dc:a6:32:52:b2:6d",
                        "port": 0,
                        "protocol": "ethernet",
                        "auto_negotiation": False,
                        "link_detected": False,
                    }
                ],
                "numa_node": 0,
                "vendor_id": "02d0",
                "product_id": "a9a6",
                "firmware_version": "01-6a2c8ad4",
            },
        ],
        "total": 2,
    },
    "storage": {
        "disks": [
            {
                "id": "mmcblk0",
                "device": "179:0",
                "type": "mmc",
                "read_only": False,
                "size": 31914983424,
                "removable": False,
                "numa_node": 0,
                "device_path": "platform-fe340000.emmc2",
                "block_size": 0,
                "rpm": 0,
                "device_id": "mmc-SC32G_0xb7dc9460",
                "partitions": [
                    {
                        "id": "mmcblk0p1",
                        "device": "179:1",
                        "read_only": False,
                        "size": 268435456,
                        "partition": 1,
                    },
                    {
                        "id": "mmcblk0p2",
                        "device": "179:2",
                        "read_only": False,
                        "size": 31645482496,
                        "partition": 2,
                    },
                ],
            },
            {
                "id": "sda",
                "device": "8:0",
                "model": "External USB 3.0",
                "type": "usb",
                "read_only": False,
                "size": 1000204883968,
                "removable": False,
                "numa_node": 0,
                "device_path": "platform-fd500000.pcie-pci-0000:01:00.0-usb-0:2:1.0-scsi-0:0:0:0",
                "block_size": 0,
                "firmware_version": "5438",
                "rpm": 0,
                "serial": "20190809001990F",
                "device_id": "usb-TOSHIBA_External_USB_3.0_20190809001990F-0:0",
                "partitions": [
                    {
                        "id": "sda1",
                        "device": "8:1",
                        "read_only": False,
                        "size": 1073741824,
                        "partition": 1,
                    },
                    {
                        "id": "sda2",
                        "device": "8:2",
                        "read_only": False,
                        "size": 21474836480,
                        "partition": 2,
                    },
                    {
                        "id": "sda3",
                        "device": "8:3",
                        "read_only": False,
                        "size": 21474836480,
                        "partition": 3,
                    },
                    {
                        "id": "sda4",
                        "device": "8:4",
                        "read_only": False,
                        "size": 956180420608,
                        "partition": 4,
                    },
                ],
            },
        ],
        "total": 8,
    },
}

# This sample is from LP:1906834
SAMPLE_LXD_RESOURCES_LP1906834 = {
    "cpu": {
        "architecture": "aarch64",
        "sockets": [
            {
                "socket": 36,
                "cache": [
                    {"level": 1, "type": "Data", "size": 32768},
                    {"level": 1, "type": "Instruction", "size": 32768},
                    {"level": 2, "type": "Unified", "size": 262144},
                ],
                "cores": [
                    {
                        "core": 0,
                        "die": 0,
                        "threads": [
                            {
                                "id": 0,
                                "numa_node": 0,
                                "thread": 0,
                                "online": True,
                                "isolated": False,
                            }
                        ],
                    },
                ],
            }
        ],
        "total": 1,
    },
    "memory": {
        "nodes": [
            {
                "numa_node": 0,
                "hugepages_used": 0,
                "hugepages_total": 0,
                "used": 1831481344,
                "total": 269430067200,
            }
        ],
        "hugepages_total": 0,
        "hugepages_used": 0,
        "hugepages_size": 2097152,
        "used": 6480928768,
        "total": 274877906944,
    },
    "gpu": {
        "cards": [],
        "total": 0,
    },
    "network": {
        "cards": [
            {
                "driver": "mlx4_core",
                "driver_version": "4.0-0",
                "ports": [
                    {
                        "id": "enP3p1s0",
                        "address": "50:6b:4b:7f:98:20",
                        "port": 0,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "1000baseKX/Full",
                            "10000baseKR/Full",
                        ],
                        "supported_ports": ["fibre"],
                        "port_type": "fibre",
                        "transceiver_type": "internal",
                        "auto_negotiation": False,
                        "link_detected": True,
                        "link_speed": 1000,
                        "link_duplex": "full",
                    },
                    {
                        "id": "enP3p1s0d1",
                        "address": "50:6b:4b:7f:98:21",
                        "port": 1,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "1000baseKX/Full",
                            "10000baseKR/Full",
                        ],
                        "supported_ports": ["fibre"],
                        "port_type": "fibre",
                        "transceiver_type": "internal",
                        "auto_negotiation": False,
                        "link_detected": False,
                    },
                ],
                "sriov": {"current_vfs": 0, "maximum_vfs": 8, "vfs": None},
                "numa_node": 0,
                "pci_address": "0003:01:00.0",
                "vendor": "Mellanox Technologies",
                "vendor_id": "15b3",
                "product": "MT27520 Family [ConnectX-3 Pro]",
                "product_id": "1007",
                "firmware_version": "2.42.5000",
            }
        ],
        "total": 1,
    },
    "storage": {
        "disks": [
            {
                "id": "nvme0n1",
                "device": "259:0",
                "model": "T408-U2",
                "type": "nvme",
                "read_only": False,
                "size": 393617408,
                "removable": False,
                "wwn": "nvme.1d82-545530352d30372d30322d4230342d30323434-543430382d5532-00000001",
                "numa_node": 0,
                "device_path": "pci-0004:01:00.0-nvme-1",
                "block_size": 4096,
                "firmware_version": "211X1B02",
                "rpm": 0,
                "serial": "TU05-07-02-B04-0244",
                "device_id": "nvme-nvme.1d82-545530352d30372d30322d4230342d30323434-543430382d5532-00000001",
                "partitions": [],
            },
            {
                "id": "nvme1n1",
                "device": "259:1",
                "model": "T408-U2",
                "type": "nvme",
                "read_only": False,
                "size": 393617408,
                "removable": False,
                "wwn": "nvme.1d82-545530352d30372d30322d4230342d30363137-543430382d5532-00000001",
                "numa_node": 0,
                "device_path": "pci-0005:01:00.0-nvme-1",
                "block_size": 4096,
                "firmware_version": "211X1B02",
                "rpm": 0,
                "serial": "TU05-07-02-B04-0617",
                "device_id": "nvme-nvme.1d82-545530352d30372d30322d4230342d30363137-543430382d5532-00000001",
                "partitions": [],
            },
            {
                "id": "sda",
                "device": "8:0",
                "model": "SAMSUNG MZ7LH960HAJR-00005",
                "type": "sata",
                "read_only": False,
                "size": 960197124096,
                "removable": False,
                "numa_node": 0,
                "device_path": "platform-APMC0D33:00-ata-1",
                "block_size": 4096,
                "firmware_version": "HXT7404Q",
                "rpm": 0,
                "serial": "S45NNA0N209754",
                "device_id": "wwn-0x5002538e0026cccb",
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
                        "size": 1073741824,
                        "partition": 2,
                    },
                    {
                        "id": "sda3",
                        "device": "8:3",
                        "read_only": False,
                        "size": 958584061952,
                        "partition": 3,
                    },
                ],
            },
            {
                "id": "sdb",
                "device": "8:16",
                "model": "Virtual HDisk0",
                "type": "usb",
                "read_only": False,
                "size": 0,
                "removable": True,
                "numa_node": 0,
                "device_path": "platform-808622B7:00-usb-0:1.2:1.0-scsi-0:0:0:0",
                "block_size": 0,
                "firmware_version": "1.00",
                "rpm": 0,
                "serial": "AAAABBBBCCCC3",
                "device_id": "usb-AMI_Virtual_HDisk0_AAAABBBBCCCC3-0:0",
                "partitions": [],
            },
            {
                "id": "sr0",
                "device": "11:0",
                "model": "Virtual CDROM0",
                "type": "cdrom",
                "read_only": False,
                "size": 0,
                "removable": True,
                "numa_node": 0,
                "device_path": "platform-808622B7:00-usb-0:1.1:1.0-scsi-0:0:0:0",
                "block_size": 0,
                "firmware_version": "1.00",
                "rpm": 0,
                "serial": "AAAABBBBCCCC1",
                "device_id": "usb-AMI_Virtual_CDROM0_AAAABBBBCCCC1-0:0",
                "partitions": [],
            },
        ],
        "total": 8,
    },
    "system": {
        "uuid": "52bcf4c0-0906-11e9-a5f5-3c18a0043e06",
        "vendor": "Lenovo",
        "product": "HR350A            7X35CTO1WW",
        "family": "Lenovo ThinkSystem HR330A/HR350A",
        "version": "7X35A000NA",
        "sku": "LENOVO_MT_OR",
        "serial": "J300LEW9",
        "type": "physical",
        "firmware": {
            "vendor": "LENOVO",
            "date": "11/29/2019",
            "version": "HVE104N-1.12",
        },
        "chassis": {
            "vendor": "Lenovo",
            "type": "Rack Mount Chassis",
            "serial": "J300LEW9",
            "version": "7X35CTO1WW",
        },
        "motherboard": {
            "vendor": "Lenovo",
            "product": "HR350A",
            "serial": "8SSB27A42854L1HF8AF0023",
            "version": "SB27A42854",
        },
    },
}
# This sample is from LP:1939456
SAMPLE_LXD_RESOURCES_NETWORK_LP1939456 = {
    "network": {
        "cards": [
            {
                "driver": "ixgbe",
                "driver_version": "5.1.0-k",
                "ports": [
                    {
                        "id": "eno1",
                        "address": "44:a8:42:ba:a3:b4",
                        "port": 0,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "1000baseKX/Full",
                            "10000baseKX4/Full",
                            "10000baseKR/Full",
                        ],
                        "supported_ports": ["fibre"],
                        "port_type": "other",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": True,
                        "link_speed": 10000,
                        "link_duplex": "full",
                    }
                ],
                "sriov": {"current_vfs": 0, "maximum_vfs": 63, "vfs": None},
                "numa_node": 0,
                "pci_address": "0000:01:00.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "82599 10 Gigabit Dual Port Backplane Connection",
                "product_id": "10f8",
                "firmware_version": "0x8000093f, 19.0.12",
            },
            {
                "driver": "ixgbe",
                "driver_version": "5.1.0-k",
                "ports": [
                    {
                        "id": "eno2",
                        "address": "44:a8:42:ba:a3:b6",
                        "port": 0,
                        "protocol": "ethernet",
                        "supported_modes": [
                            "1000baseKX/Full",
                            "10000baseKX4/Full",
                            "10000baseKR/Full",
                        ],
                        "supported_ports": ["fibre"],
                        "port_type": "other",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": False,
                    }
                ],
                "sriov": {"current_vfs": 0, "maximum_vfs": 63, "vfs": None},
                "numa_node": 0,
                "pci_address": "0000:01:00.1",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "82599 10 Gigabit Dual Port Backplane Connection",
                "product_id": "10f8",
                "firmware_version": "0x8000093f, 19.0.12",
            },
            {
                "driver": "mlx4_core",
                "driver_version": "4.9-3.1.5",
                "ports": [
                    {
                        "id": "ibp4s0",
                        "address": "a0:00:02:20:fe:80:00:00:00:00:00:00:e4:1d:2d:03:00:4f:06:e1",
                        "port": 0,
                        "protocol": "infiniband",
                        "port_type": "other",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": False,
                        "infiniband": {
                            "issm_name": "issm0",
                            "issm_device": "231:64",
                            "mad_name": "umad0",
                            "mad_device": "231:0",
                            "verb_name": "uverbs0",
                            "verb_device": "231:192",
                        },
                    },
                    {
                        "id": "ibp4s0d1",
                        "address": "a0:00:03:00:fe:80:00:00:00:00:00:00:e4:1d:2d:03:00:4f:06:e2",
                        "port": 1,
                        "protocol": "infiniband",
                        "port_type": "other",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": False,
                        "infiniband": {
                            "issm_name": "issm1",
                            "issm_device": "231:65",
                            "mad_name": "umad1",
                            "mad_device": "231:1",
                            "verb_name": "uverbs0",
                            "verb_device": "231:192",
                        },
                    },
                ],
                "numa_node": 0,
                "pci_address": "0000:04:00.0",
                "vendor": "Mellanox Technologies",
                "vendor_id": "15b3",
                "product": "MT27500 Family [ConnectX-3]",
                "product_id": "1003",
                "firmware_version": "2.36.5000",
            },
            {
                "driver": "cdc_ether",
                "driver_version": "5.4.0-80-generic",
                "ports": [
                    {
                        "id": "idrac",
                        "address": "10:98:36:99:7d:9e",
                        "port": 0,
                        "protocol": "ethernet",
                        "auto_negotiation": False,
                        "link_detected": False,
                    }
                ],
                "numa_node": 0,
                "firmware_version": "CDC Ethernet Device",
                "usb_address": "1:4",
            },
        ],
        "total": 4,
    }
}

SAMPLE_LXD_NETWORK_LP1939456 = {
    "bond0": {
        "addresses": [
            {
                "family": "inet",
                "address": "10.206.123.143",
                "netmask": "24",
                "scope": "global",
            },
            {
                "family": "inet6",
                "address": "fe80::60af:27ff:fe86:a7b5",
                "netmask": "64",
                "scope": "link",
            },
        ],
        "counters": {
            "bytes_received": 61539371832,
            "bytes_sent": 12363017514,
            "packets_received": 46790270,
            "packets_sent": 26046855,
        },
        "hwaddr": "62:af:27:86:a7:b5",
        "mtu": 1500,
        "state": "up",
        "type": "broadcast",
        "bond": {
            "mode": "802.3ad",
            "transmit_policy": "layer2",
            "up_delay": 0,
            "down_delay": 0,
            "mii_frequency": 100,
            "mii_state": "up",
            "lower_devices": ["eno2", "eno1"],
        },
        "bridge": None,
        "vlan": None,
    },
    "bond0.1": {
        "addresses": [
            {
                "family": "inet",
                "address": "10.128.210.1",
                "netmask": "20",
                "scope": "global",
            },
            {
                "family": "inet6",
                "address": "fe80::60af:27ff:fe86:a7b5",
                "netmask": "64",
                "scope": "link",
            },
        ],
        "counters": {
            "bytes_received": 3264146,
            "bytes_sent": 1093111,
            "packets_received": 57665,
            "packets_sent": 5266,
        },
        "hwaddr": "62:af:27:86:a7:b5",
        "mtu": 1500,
        "state": "up",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": {"lower_device": "bond0", "vid": 1},
    },
    "bond0.240": {
        "addresses": [
            {
                "family": "inet",
                "address": "10.240.0.1",
                "netmask": "24",
                "scope": "global",
            },
            {
                "family": "inet6",
                "address": "fe80::60af:27ff:fe86:a7b5",
                "netmask": "64",
                "scope": "link",
            },
        ],
        "counters": {
            "bytes_received": 7156780,
            "bytes_sent": 1035310179,
            "packets_received": 116634,
            "packets_sent": 75712,
        },
        "hwaddr": "62:af:27:86:a7:b5",
        "mtu": 1500,
        "state": "up",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": {"lower_device": "bond0", "vid": 240},
    },
    "eno1": {
        "addresses": [],
        "counters": {
            "bytes_received": 11639365749,
            "bytes_sent": 3271900148,
            "packets_received": 9125767,
            "packets_sent": 5627403,
        },
        "hwaddr": "62:af:27:86:a7:b5",
        "mtu": 1500,
        "state": "up",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "eno2": {
        "addresses": [],
        "counters": {
            "bytes_received": 49900006083,
            "bytes_sent": 9091117366,
            "packets_received": 37664503,
            "packets_sent": 20419452,
        },
        "hwaddr": "62:af:27:86:a7:b5",
        "mtu": 1500,
        "state": "down",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "ibp4s0": {
        "addresses": [],
        "counters": {
            "bytes_received": 0,
            "bytes_sent": 0,
            "packets_received": 0,
            "packets_sent": 0,
        },
        "hwaddr": "a0:00:02:20:fe:80:00:00:00:00:00:00:e4:1d:2d:03:00:4f:06:e1",
        "mtu": 4092,
        "state": "down",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "ibp4s0d1": {
        "addresses": [],
        "counters": {
            "bytes_received": 0,
            "bytes_sent": 0,
            "packets_received": 0,
            "packets_sent": 0,
        },
        "hwaddr": "a0:00:03:00:fe:80:00:00:00:00:00:00:e4:1d:2d:03:00:4f:06:e2",
        "mtu": 4092,
        "state": "down",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
    "idrac": {
        "addresses": [],
        "counters": {
            "bytes_received": 0,
            "bytes_sent": 0,
            "packets_received": 0,
            "packets_sent": 0,
        },
        "hwaddr": "10:98:36:99:7d:9e",
        "mtu": 1500,
        "state": "down",
        "type": "broadcast",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
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
        "counters": {
            "bytes_received": 15773896406,
            "bytes_sent": 15773896406,
            "packets_received": 14090610,
            "packets_sent": 14090610,
        },
        "hwaddr": "",
        "mtu": 65536,
        "state": "up",
        "type": "loopback",
        "bond": None,
        "bridge": None,
        "vlan": None,
    },
}


KERNEL_CMDLINE_OUTPUT = (
    "BOOT_IMAGE=http://10.245.136.6:5248/images/ubuntu/amd64/generic/bionic/"
    "daily/boot-kernel nomodeset ro root=squash:http://10.245.136.6:5248/"
    "images/ubuntu/amd64/generic/bionic/daily/squashfs "
    "ip=::::flying-marmot:BOOTIF ip6=off overlayroot=tmpfs "
    "overlayroot_cfgdisk=disabled cc:{{'datasource_list': ['MAAS']}}"
    "end_cc cloud-config-url=http://10-245-136-0--21.maas-internal:5248/MAAS/"
    "metadata/latest/by-id/m3e8ks/?op=get_preseed apparmor=0 "
    "log_host=10.245.136.6 log_port=5247 initrd=http://10.245.136.6:5248/"
    "images/ubuntu/amd64/generic/bionic/daily/boot-initrd "
    "BOOTIF=01-{mac_address}\n"
)


def make_lxd_host_info(
    api_extensions=None,
    api_version=None,
    kernel_architecture=None,
    kernel_version=None,
    os_name=None,
    os_version=None,
    server_name=None,
):
    if api_extensions is None:
        api_extensions = [
            "resources",
            "resources_v2",
            "api_os",
            "resources_system",
            "resources_usb_pci",
        ]
    if api_version is None:
        api_version = "1.0"
    if kernel_architecture is None:
        kernel_architecture = random.choice(
            ["i686", "x86_64", "aarch64", "ppc64le", "s390x", "mips", "mips64"]
        )
    if kernel_version is None:
        kernel_version = factory.make_name("kernel_version")
    if os_name is None:
        os_name = "Ubuntu"
    if os_version is None:
        os_version = random.choice(["16.04", "18.04", "20.04"])
    if server_name is None:
        server_name = factory.make_hostname()
    return {
        "api_extensions": api_extensions,
        "api_version": api_version,
        "environment": {
            "kernel": "Linux",
            "kernel_architecture": kernel_architecture,
            "kernel_version": kernel_version,
            "os_name": os_name,
            "os_version": os_version,
            "server": "maas-machine-resources",
            "server_name": server_name,
            "server_version": "4.0.0",
        },
    }


def make_lxd_pcie_device(numa_node=0, pci_address=None):
    if pci_address is None:
        pci_address = "{}:{}:{}.{}".format(
            factory.make_hex_string(size=4),
            factory.make_hex_string(size=2),
            factory.make_hex_string(size=2),
            factory.make_hex_string(size=1),
        )
    return {
        "driver": factory.make_name("driver"),
        "driver_version": factory.make_name("driver-version"),
        "numa_node": numa_node,
        "pci_address": pci_address,
        "product": factory.make_name("product"),
        "product_id": factory.make_hex_string(size=4),
        "vendor": factory.make_name("vendor"),
        "vendor_id": factory.make_hex_string(size=4),
        "iommu_group": 0,
        "vpd": {
            "entries": {
                "PN": factory.make_hex_string(size=4),
                "SN": factory.make_hex_string(size=4),
            }
        },
    }


def make_lxd_usb_device(bus_address=None, device_address=None):
    if bus_address is None:
        bus_address = random.randint(0, 2**16)
    if device_address is None:
        device_address = random.randint(0, 2**16)
    return {
        "bus_address": bus_address,
        "device_address": device_address,
        "interfaces": [
            {
                "class": factory.make_name("class"),
                "class_id": random.randint(0, 256),
                "driver": factory.make_name("driver"),
                "driver_version": factory.make_name("driver_version"),
                "number": i,
                "subclass": factory.make_name("subclass"),
                "subclass_id": random.randint(0, 256),
            }
            for i in range(0, random.randint(1, 3))
        ],
        "product": factory.make_name("product"),
        "product_id": factory.make_hex_string(size=4),
        "speed": 480,
        "vendor": factory.make_name("vendor"),
        "vendor_id": factory.make_hex_string(size=4),
    }


def make_lxd_output(
    resources=None,
    networks=None,
    api_extensions=None,
    api_version=None,
    kernel_architecture=None,
    kernel_version=None,
    os_name=None,
    os_version=None,
    server_name=None,
    virt_type=None,
    uuid=None,
):
    if not resources:
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
    if not networks:
        networks = deepcopy(SAMPLE_LXD_NETWORKS)
    ret = {
        **make_lxd_host_info(
            api_extensions,
            api_version,
            kernel_architecture,
            kernel_version,
            os_name,
            os_version,
            server_name,
        ),
        "resources": resources,
        "networks": networks,
    }
    ret["resources"]["system"] = make_lxd_system_info(virt_type, uuid)
    return ret


def make_lxd_output_json(*args, **kwargs):
    return json.dumps(make_lxd_output(*args, **kwargs)).encode()


def create_numa_nodes(node):
    # This NUMA node information matches SAMPLE_LXD_RESOURCES
    # so if that changes, this needs to be updated.
    numa_nodes = {
        0: {"memory": int(16691519488 / 2 / 1024 / 1024), "cores": [0, 1]},
        1: {"memory": int(16691519488 / 2 / 1024 / 1024), "cores": [2, 3]},
    }
    numa_nodes = [
        NUMANode.objects.update_or_create(
            node=node,
            index=numa_index,
            defaults={
                "memory": numa_data["memory"],
                "cores": numa_data["cores"],
            },
        )[0]
        for numa_index, numa_data in numa_nodes.items()
    ]

    return numa_nodes


def make_lldp_output(macs):
    """Return an example raw lldp output containing the given MACs."""
    interfaces = "\n".join(
        lldp_output_interface_template % mac for mac in macs
    )
    script = (lldp_output_template % interfaces).encode("utf8")
    return bytes(script)


class TestDetectSwitchVendorModelDMIScenarios(MAASServerTestCase):
    scenarios = (
        (
            "accton_wedge40_1",
            {
                "modaliases": ["dmi:svnIntel:pnEPGSVR"],
                "dmi_data": frozenset({"svnIntel", "pnEPGSVR"}),
                "result": ("accton", "wedge40"),
            },
        ),
        (
            "accton_wedge40_2",
            {
                "modaliases": ["dmi:svnJoytech:pnWedge-AC-F20-001329"],
                "dmi_data": frozenset({"svnJoytech", "pnWedge-AC-F20-001329"}),
                "result": ("accton", "wedge40"),
            },
        ),
        (
            "accton_wedge100",
            {
                "modaliases": [
                    "dmi:svnTobefilledbyO.E.M.:pnTobefilledbyO.E.M.:"
                    "rnPCOM-B632VG-ECC-FB-ACCTON-D"
                ],
                "dmi_data": frozenset(
                    {
                        "svnTobefilledbyO.E.M.",
                        "pnTobefilledbyO.E.M.",
                        "rnPCOM-B632VG-ECC-FB-ACCTON-D",
                    }
                ),
                "result": ("accton", "wedge100"),
            },
        ),
        (
            "mellanox_sn2100",
            {
                "modaliases": [
                    'dmi:svnMellanoxTechnologiesLtd.:pn"MSN2100-CB2FO"'
                ],
                "dmi_data": frozenset(
                    {"svnMellanoxTechnologiesLtd.", 'pn"MSN2100-CB2FO"'}
                ),
                "result": ("mellanox", "sn2100"),
            },
        ),
    )

    def test_detect_switch_vendor_model(self):
        detected = detect_switch_vendor_model(self.dmi_data)
        self.assertEqual(self.result, detected)

    def test_get_dmi_data(self):
        dmi_data = get_dmi_data(self.modaliases)
        self.assertEqual(self.dmi_data, dmi_data)


class TestDetectSwitchVendorModel(MAASServerTestCase):
    def test_detect_switch_vendor_model_returns_none_by_default(self):
        detected = detect_switch_vendor_model(set())
        self.assertEqual((None, None), detected)


TEST_MODALIASES = [
    "pci:v00001A03d00001150sv000015D9sd00000888bc06sc04i00",
    "pci:v00001A03d00002000sv000015D9sd00000888bc03sc00i00",
    "pci:v00008086d00001533sv000015D9sd00001533bc02sc00i00",
    "pci:v00008086d000015B7sv000015D9sd000015B7bc02sc00i00",
    "pci:v00008086d00001918sv000015D9sd00000888bc06sc00i00",
    "pci:v00008086d0000A102sv000015D9sd00000888bc01sc06i01",
    "pci:v00008086d0000A118sv000015D9sd00000888bc06sc04i00",
    "pci:v00008086d0000A119sv000015D9sd00000888bc06sc04i00",
    "pci:v00008086d0000A11Asv000015D9sd00000888bc06sc04i00",
    "pci:v00008086d0000A121sv000015D9sd00000888bc05sc80i00",
    "pci:v00008086d0000A123sv000015D9sd00000888bc0Csc05i00",
    "pci:v00008086d0000A12Fsv000015D9sd00000888bc0Csc03i30",
    "pci:v00008086d0000A131sv000015D9sd00000888bc11sc80i00",
    "pci:v00008086d0000A13Dsv000015D9sd00000888bc07sc00i02",
    "pci:v00008086d0000A149sv000015D9sd00000888bc06sc01i00",
    "pci:v00008086d0000A170sv000015D9sd00000888bc04sc03i00",
    "usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip01in00",
    "usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip02in01",
    "usb:v0557p7000d0000dc09dsc00dp01ic09isc00ip00in00",
    "usb:v174Cp07D1d1000dc00dsc00dp00ic08isc06ip50in00",
    "usb:v1D6Bp0002d0410dc09dsc00dp01ic09isc00ip00in00",
    "usb:v1D6Bp0003d0410dc09dsc00dp03ic09isc00ip00in00",
]


class TestFilterModaliases(MAASTestCase):
    scenarios = (
        (
            "modalias_wildcard_multiple_match",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntu:version14.04",
                    "beverage:typeCoffee:variantEspresso",
                    "beverage:typeCoffee:variantCappuccino",
                    "beverage:typeTea:variantProperBritish",
                ],
                "candidates": ["beverage:typeCoffee:*"],
                "pci": None,
                "usb": None,
                "result": [
                    "beverage:typeCoffee:variantEspresso",
                    "beverage:typeCoffee:variantCappuccino",
                ],
            },
        ),
        (
            "modalias_multiple_wildcard_match",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntu:version14.04",
                    "beverage:typeCoffee:variantEspresso",
                    "beverage:typeCoffee:variantCappuccino",
                    "beverage:typeTea:variantProperBritish",
                ],
                "candidates": [
                    "os:vendorCanonical:*",
                    "os:*:productUbuntu:*",
                    "beverage:*ProperBritish",
                ],
                "pci": None,
                "usb": None,
                "result": [
                    "os:vendorCanonical:productUbuntu:version14.04",
                    "beverage:typeTea:variantProperBritish",
                ],
            },
        ),
        (
            "modalias_exact_match",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntu:version14.04",
                    "beverage:typeCoffee:variantEspresso",
                    "beverage:typeCoffee:variantCappuccino",
                    "beverage:typeTea:variantProperBritish",
                ],
                "candidates": [
                    "os:vendorCanonical:productUbuntu:version14.04"
                ],
                "pci": None,
                "usb": None,
                "result": ["os:vendorCanonical:productUbuntu:version14.04"],
            },
        ),
        (
            "pci_malformed_string",
            {
                "modaliases": TEST_MODALIASES,
                "candidates": None,
                "pci": ["8086"],
                "usb": None,
                "result": [],
            },
        ),
        (
            "pci_exact_match",
            {
                "modaliases": TEST_MODALIASES,
                "candidates": None,
                "pci": ["8086:1918"],
                "usb": None,
                "result": [
                    "pci:v00008086d00001918sv000015D9sd00000888bc06sc00i00"
                ],
            },
        ),
        (
            "pci_wildcard_match",
            {
                "modaliases": TEST_MODALIASES,
                "candidates": None,
                "pci": ["1a03:*"],
                "usb": None,
                "result": [
                    "pci:v00001A03d00001150sv000015D9sd00000888bc06sc04i00",
                    "pci:v00001A03d00002000sv000015D9sd00000888bc03sc00i00",
                ],
            },
        ),
        (
            "usb_malformed_string",
            {
                "modaliases": TEST_MODALIASES,
                "candidates": None,
                "pci": None,
                "usb": ["174c"],
                "result": [],
            },
        ),
        (
            "usb_exact_match",
            {
                "modaliases": TEST_MODALIASES,
                "candidates": None,
                "pci": None,
                "usb": ["174c:07d1"],
                "result": [
                    "usb:v174Cp07D1d1000dc00dsc00dp00ic08isc06ip50in00"
                ],
            },
        ),
        (
            "usb_wildcard_match",
            {
                "modaliases": TEST_MODALIASES,
                "candidates": None,
                "pci": None,
                "usb": ["0557:*"],
                "result": [
                    "usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip01in00",
                    "usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip02in01",
                    "usb:v0557p7000d0000dc09dsc00dp01ic09isc00ip00in00",
                ],
            },
        ),
    )

    def test_filter_modaliases(self):
        matches = filter_modaliases(
            self.modaliases, self.candidates, pci=self.pci, usb=self.usb
        )
        self.assertEqual(self.result, matches)


class TestDetectHardware(MAASServerTestCase):
    scenarios = (
        (
            "caffeine_fueled_ubuntu_classic",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntu:version14.04",
                    "beverage:typeCoffee:variantEspresso",
                    "beverage:typeCoffee:variantCappuccino",
                    "beverage:typeTea:variantProperBritish",
                ],
                "expected_match_indexes": [0, 1, 2],
                "expected_ruled_out_indexes": [3],
            },
        ),
        (
            "caffeine_fueled_ubuntu_core",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntuCore:version16.04",
                    "beverage:typeCoffee:variantEspresso",
                    "beverage:typeCoffee:variantCappuccino",
                    "beverage:typeTea:variantProperBritish",
                ],
                "expected_match_indexes": [0, 1, 3],
                "expected_ruled_out_indexes": [2],
            },
        ),
        (
            "ubuntu_classic",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntu:version14.04"
                ],
                "expected_match_indexes": [1, 2],
                "expected_ruled_out_indexes": [0, 3],
            },
        ),
        (
            "ubuntu_core",
            {
                "modaliases": [
                    "os:vendorCanonical:productUbuntuCore:version16.04"
                ],
                "expected_match_indexes": [1, 3],
                "expected_ruled_out_indexes": [0, 2],
            },
        ),
        (
            "none_of_the_above",
            {
                "modaliases": [
                    "xos:vendorCanonical:productUbuntuCore:version16.04",
                    "xbeverage:typeCoffee:variantEspresso",
                    "xbeverage:typeCoffee:variantCappuccino",
                    "xbeverage:typeTea:variantProperBritish",
                ],
                "expected_match_indexes": [],
                "expected_ruled_out_indexes": [0, 1, 2, 3],
            },
        ),
    )

    hardware_database = [
        {
            "modaliases": ["beverage:typeCoffee:*", "beverage:typeTea:*"],
            "tag": "caffeine-fueled-sprint",
            "comment": "Caffeine-fueled sprint.",
        },
        {
            "modaliases": ["os:vendorCanonical:productUbuntu*"],
            "tag": "ubuntu",
            "comment": "Ubuntu",
        },
        {
            "modaliases": ["os:vendorCanonical:productUbuntu:*"],
            "tag": "ubuntu-classic",
            "comment": "Ubuntu Classic",
        },
        {
            "modaliases": ["os:vendorCanonical:productUbuntuCore:*"],
            "tag": "ubuntu-core",
            "comment": "Ubuntu Core",
        },
    ]

    def test_determine_hardware_matches(self):
        discovered, ruled_out = determine_hardware_matches(
            self.modaliases, self.hardware_database
        )
        expected_matches = [
            self.hardware_database[index].copy()
            for index in self.expected_match_indexes
        ]
        # Note: determine_hardware_matches() adds the matches as informational.
        for item in discovered:
            self.expectThat(
                item["matches"],
                Equals(filter_modaliases(self.modaliases, item["modaliases"])),
            )
            # Delete this so we can compare the matches to what was expected.
            del item["matches"]
        expected_ruled_out = [
            self.hardware_database[index]
            for index in self.expected_ruled_out_indexes
        ]
        self.assertEqual(expected_matches, discovered)
        self.assertEqual(expected_ruled_out, ruled_out)

    def test_retag_node_for_hardware_by_modalias__precreate_parent(self):
        node = factory.make_Node()
        parent_tag = factory.make_Tag()
        parent_tag_name = parent_tag.name
        # Need to pre-create these so the code can remove them.
        expected_removed = {
            factory.make_Tag(name=self.hardware_database[index]["tag"])
            for index in self.expected_ruled_out_indexes
        }
        for tag in expected_removed:
            node.tags.add(tag)
        added, removed = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database
        )
        expected_added = {
            Tag.objects.get(name=self.hardware_database[index]["tag"])
            for index in self.expected_match_indexes
        }
        if len(expected_added) > 0:
            expected_added.add(parent_tag)
        else:
            expected_removed.add(parent_tag)
        self.assertEqual(expected_added, added)
        self.assertEqual(expected_removed, removed)
        # Run again to confirm that we added the same tags.
        added, removed = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database
        )
        self.assertEqual(expected_added, added)

    def test_retag_node_for_hardware_by_modalias__adds_parent_tag(self):
        node = factory.make_Node()
        parent_tag_name = "parent-tag-name"
        added, _ = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database
        )
        # Test that the parent tag was created if the hardware matched.
        if len(added) > 0:
            self.assertIsNotNone(Tag.objects.get(name=parent_tag_name))


class TestAddSwitchVendorModelTags(MAASServerTestCase):
    def test_sets_wedge40_kernel_opts(self):
        node = factory.make_Node()
        add_switch_vendor_model_tags(node, "accton", "wedge40")
        tags = set(node.tags.all().values_list("name", flat=True))
        self.assertEqual({"accton", "wedge40"}, tags)
        tag = Tag.objects.get(name="wedge40")
        self.assertEqual("console=tty0 console=ttyS1,57600n8", tag.kernel_opts)

    def test_sets_wedge100_kernel_opts(self):
        node = factory.make_Node()
        add_switch_vendor_model_tags(node, "accton", "wedge100")
        tags = set(node.tags.all().values_list("name", flat=True))
        self.assertEqual({"accton", "wedge100"}, tags)
        tag = Tag.objects.get(name="wedge100")
        self.assertEqual("console=tty0 console=ttyS4,57600n8", tag.kernel_opts)


class TestCreateMetadataByModalias(MAASServerTestCase):
    scenarios = (
        (
            "switch_trident2",
            {
                "modaliases": b"pci:xxx\n"
                b"pci:v000014E4d0000B850sv0sd1bc2sc3i4\n"
                b"dmi:svnJoytech:pnWedge-AC-F20-001329\n"
                b"pci:yyy\n",
                "expected_tags": {
                    "accton",
                    "switch",
                    "bcm-trident2-asic",
                    "wedge40",
                },
            },
        ),
        (
            "switch_tomahawk",
            {
                "modaliases": b"pci:xxx\n"
                b"pci:v000014E4d0000B960sv0sd1bc2sc3i4\n"
                b"dmi:svnTobefilledbyO.E.M.:pnTobefilledbyO.E.M.:"
                b"rnPCOM-B632VG-ECC-FB-ACCTON-D\n"
                b"pci:yyy\n",
                "expected_tags": {
                    "accton",
                    "switch",
                    "bcm-tomahawk-asic",
                    "wedge100",
                },
            },
        ),
        (
            "no_matcj",
            {
                "modaliases": b"pci:xxx\n" b"pci:yyy\n",
                "expected_tags": set(),
            },
        ),
    )

    def test_tags_node_appropriately(self):
        node = factory.make_Node()
        create_metadata_by_modalias(node, self.modaliases, 0)
        tags = set(node.tags.all().values_list("name", flat=True))
        self.assertEqual(self.expected_tags, tags)


class TestUpdateFruidMetadata(MAASServerTestCase):
    # This is an actual response returned by a Facebook Wedge 100.
    SAMPLE_RESPONSE = b"""
{
  "Actions": [],
  "Resources": [],
  "Information": {

    "Assembled At": "Accton",
    "CRC8": "0x3f",
    "Extended MAC Address Size": "128",
    "Extended MAC Base": "A8:2B:B5:2F:FD:32",
    "Facebook PCB Part Number": "142-000001-38",
    "Facebook PCBA Part Number": "NP3-ZZ7632-02",
    "Local MAC": "A8:2B:B5:2F:FD:31",
    "Location on Fabric": "WEDGE100",
    "ODM PCBA Part Number": "NP3ZZ7632025",
    "ODM PCBA Serial Number": "AH19058615",
    "PCB Manufacturer": "ISU",
    "Product Asset Tag": "",
    "Product Name": "Wedge100ACFO",
    "Product Part Number": "76-32055A",
    "Product Production State": "4",
    "Product Serial Number": "AH19058615",
    "Product Sub-Version": "1",
    "Product Version": "1",
    "System Assembly Part Number": "CP3-ZZ7632-05",
    "System Manufacturer": "Accton",
    "System Manufacturing Date": "05-16-17",
    "Version": "1"
  }
}
    """

    def test_no_output_creates_no_metadata(self):
        node = factory.make_Node()
        update_node_fruid_metadata(node, b"", 0)

        metadata = node.get_metadata()
        self.assertEqual({}, metadata)

    def test_parsed_values(self):
        node = factory.make_Node()
        update_node_fruid_metadata(node, self.SAMPLE_RESPONSE, 0)

        metadata = node.get_metadata()
        self.assertEqual(
            {
                NODE_METADATA.PHYSICAL_MODEL_NAME: "Wedge100ACFO",
                NODE_METADATA.PHYSICAL_SERIAL_NUM: "AH19058615",
                NODE_METADATA.PHYSICAL_HARDWARE_REV: "1",
                NODE_METADATA.PHYSICAL_MFG_NAME: "Accton",
            },
            metadata,
        )


class TestProcessLXDResults(MAASServerTestCase):
    def assertSystemInformation(self, node, data):
        if "resources" in data:
            data = data["resources"]
        if "system" in data:
            data = deepcopy(data["system"])
        else:
            data = deepcopy(data)

        system_type = data.get("type")
        if system_type and system_type != "physical":
            self.assertTrue(node.tags.filter(name="virtual").exists())
        else:
            self.assertFalse(node.tags.filter(name="virtual").exists())
        del data["type"]

        for k, v in data.items():
            if isinstance(v, dict):
                for x, w in v.items():
                    if not w or w in ["0123456789", "none"]:
                        del data[k][v][x]
            else:
                if not v or v in ["0123456789", "none"]:
                    del data[k]

        pulled_data = {"uuid": node.hardware_uuid}
        for nmd in node.nodemetadata_set.all():
            if "_" not in nmd.key:
                continue
            if nmd.key.count("_") == 2:
                main_section, subsection, key = nmd.key.split("_")
                section = f"{main_section}_{subsection}"
            else:
                section, key = nmd.key.split("_")
            if section == "system":
                pulled_data[key] = nmd.value
            elif section == "mainboard":
                if "motherboard" not in pulled_data:
                    pulled_data["motherboard"] = {}
                pulled_data["motherboard"][key] = nmd.value
            elif section == "mainboard_firmware":
                if "firmware" not in pulled_data:
                    pulled_data["firmware"] = {}
                pulled_data["firmware"][key] = nmd.value
            elif section == "chassis":
                if "chassis" not in pulled_data:
                    pulled_data["chassis"] = {}
                pulled_data["chassis"][key] = nmd.value

        self.assertDictEqual(data, pulled_data)

    def test_invalid_json_logs_event(self):
        node = factory.make_Node()
        self.assertRaises(
            ValueError, process_lxd_results, node, b"not json", 0
        )
        [event] = Event.objects.all()
        self.assertEqual(event.node, node)
        self.assertEqual(event.type.name, EVENT_TYPES.SCRIPT_RESULT_ERROR)
        self.assertEqual(
            event.description,
            "Failed processing commissioning data: invalid JSON data",
        )

    def test_validate_storage_extra(self):
        node = factory.make_Node()
        uuid = factory.make_UUID()
        data = make_lxd_output(uuid=uuid)
        data["storage-extra"] = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                },
            },
            "mounts": {},
        }
        process_lxd_results(node, json.dumps(data).encode(), 0)
        node = reload_object(node)
        self.assertEqual(uuid, node.hardware_uuid)

    def test_invalid_storage_extra(self):
        node = factory.make_Node()
        uuid = factory.make_UUID()
        data = make_lxd_output(uuid=uuid)
        data["storage-extra"] = {"invalid": "data"}
        self.assertRaises(
            ConfigError,
            process_lxd_results,
            node,
            json.dumps(data).encode(),
            0,
        )
        [event] = Event.objects.all()
        self.assertEqual(event.node, node)
        self.assertEqual(event.type.name, EVENT_TYPES.SCRIPT_RESULT_ERROR)
        self.assertEqual(
            event.description,
            "Failed processing commissioning data: "
            "Invalid config at top level: "
            "Additional properties are not allowed ('invalid' was unexpected)",
        )

    def test_errors_if_not_supported_lxd_api_ver(self):
        node = factory.make_Node()
        self.assertRaises(
            AssertionError,
            process_lxd_results,
            node,
            make_lxd_output_json(
                api_version=f"{random.randint(2, 10)}.{random.randint(0, 10)}"
            ),
            0,
        )

    def test_errors_if_missing_api_extension(self):
        node = factory.make_Node()
        required_extensions = {
            "resources",
            "resources_v2",
            "api_os",
            "resources_system",
        }
        for missing_extension in required_extensions:
            extensions = required_extensions.difference([missing_extension])
            self.assertRaises(
                AssertionError,
                process_lxd_results,
                node,
                make_lxd_output_json(api_extensions=list(extensions)),
                0,
            )

    def test_sets_architecture(self):
        node = factory.make_Node()
        kernel_arch, deb_arch = random.choice(
            [
                ("i686", "i386/generic"),
                ("x86_64", "amd64/generic"),
                ("aarch64", "arm64/generic"),
                ("ppc64le", "ppc64el/generic"),
                ("s390x", "s390x/generic"),
                ("mips", "mips/generic"),
                ("mips64", "mips64el/generic"),
            ]
        )
        process_lxd_results(
            node, make_lxd_output_json(kernel_architecture=kernel_arch), 0
        )
        node = reload_object(node)
        self.assertEqual(deb_arch, node.architecture)

    def test_keeps_subarchitecture(self):
        arch = "amd64/somesubarch"
        node = factory.make_Node(architecture=arch)
        process_lxd_results(
            node, make_lxd_output_json(kernel_architecture="x86_64"), 0
        )
        node = reload_object(node)
        self.assertEqual(node.architecture, arch)

    def test_updates_arch_subarch_if_different_arch(self):
        arch = "ppc64/somesubarch"
        node = factory.make_Node(architecture=arch)
        process_lxd_results(
            node, make_lxd_output_json(kernel_architecture="x86_64"), 0
        )
        node = reload_object(node)
        self.assertEqual(node.architecture, "amd64/generic")

    def test_sets_uuid(self):
        node = factory.make_Node()
        uuid = factory.make_UUID()
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        node = reload_object(node)
        self.assertEqual(uuid, node.hardware_uuid)

    def test_sets_empty_uuid(self):
        node = factory.make_Node()
        # LXD reports the uuid as "" if the machine doesn't have one
        # set.
        uuid = ""
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        node = reload_object(node)
        # In the DB, we store the missing UUID as None, so that the
        # check for unique UUIDs isn't triggered.
        self.assertIsNone(node.hardware_uuid)

    def test_removes_duplicate_uuid(self):
        uuid = factory.make_UUID()
        duplicate_uuid_node = factory.make_Node(hardware_uuid=uuid)
        node = factory.make_Node()
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        self.assertIsNone(reload_object(node).hardware_uuid)
        self.assertIsNone(reload_object(duplicate_uuid_node).hardware_uuid)

    def test_ignores_invalid_uuid(self):
        uuid = factory.make_name("invalid_uuid")
        node = factory.make_Node()
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        self.assertIsNone(reload_object(node).hardware_uuid)

    def test_sets_os_for_deployed_node(self):
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        ubuntu_info = UbuntuDistroInfo()
        ubuntu_release = random.choice(
            [row.__dict__ for row in ubuntu_info._releases]
        )
        os_version = ubuntu_release["version"].replace(" LTS", "")
        process_lxd_results(
            node,
            make_lxd_output_json(os_version=os_version),
            0,
        )
        node = reload_object(node)
        self.assertEqual("ubuntu", node.osystem)
        self.assertEqual(ubuntu_release["series"], node.distro_series)

    def test_doesnt_set_os_for_controller_if_blank(self):
        osystem = factory.make_name("osystem")
        distro_series = factory.make_name("distro_series")
        node = factory.make_Machine(
            osystem=osystem,
            distro_series=distro_series,
            status=NODE_STATUS.DEPLOYED,
        )
        process_lxd_results(
            node, make_lxd_output_json(os_name="", os_version=""), 0
        )
        node = reload_object(node)
        self.assertEqual(osystem, node.osystem)
        self.assertEqual(distro_series, node.distro_series)

    def test_ignores_os_for_commissioning_machine(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING,
            osystem="centos",
            distro_series="8",
        )
        hostname = node.hostname
        process_lxd_results(node, make_lxd_output_json(), 0)
        node = reload_object(node)
        self.assertEqual("centos", node.osystem)
        self.assertEqual("8", node.distro_series)
        self.assertEqual(hostname, node.hostname)

    def test_does_not_initialize_node_network_information_if_pod(self):
        pod = factory.make_Pod()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        pod.hints.nodes.add(node)
        mock_set_initial_net_config = self.patch(
            node_module.Node, "set_initial_networking_configuration"
        )
        process_lxd_results(node, make_lxd_output_json(), 0)
        self.assertThat(mock_set_initial_net_config, MockNotCalled())
        # Verify network device information was collected
        self.assertEqual(
            ["Intel Corporation", "Intel Corporation", "Intel Corporation"],
            [
                iface.vendor
                for iface in node.current_config.interface_set.all()
            ],
        )

    def test_updates_memory(self):
        node = factory.make_Node()
        node.memory = random.randint(4096, 8192)
        node.save()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        process_lxd_results(node, make_lxd_output_json(), 0)
        node = reload_object(node)
        self.assertEqual(round(16691519488 / 1024 / 1024), node.memory)

    def test_updates_model_and_cpu_speed_from_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        process_lxd_results(node, make_lxd_output_json(), 0)
        node = reload_object(node)
        self.assertEqual(2400, node.cpu_speed)
        nmd = NodeMetadata.objects.get(node=node, key="cpu_model")
        self.assertEqual("Intel(R) Core(TM) i7-4700MQ CPU", nmd.value)

    def test_updates_cpu_speed_with_max_frequency_when_not_in_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        NO_SPEED_IN_NAME = deepcopy(SAMPLE_LXD_RESOURCES)
        NO_SPEED_IN_NAME["cpu"]["sockets"][0][
            "name"
        ] = "Intel(R) Core(TM) i7-4700MQ CPU"
        process_lxd_results(node, make_lxd_output_json(NO_SPEED_IN_NAME), 0)
        node = reload_object(node)
        self.assertEqual(3400, node.cpu_speed)

    def test_updates_cpu_speed_with_current_frequency_when_not_in_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        NO_NAME_OR_MAX_FREQ = deepcopy(SAMPLE_LXD_RESOURCES)
        del NO_NAME_OR_MAX_FREQ["cpu"]["sockets"][0]["name"]
        del NO_NAME_OR_MAX_FREQ["cpu"]["sockets"][0]["frequency_turbo"]
        process_lxd_results(node, make_lxd_output_json(NO_NAME_OR_MAX_FREQ), 0)
        node = reload_object(node)
        self.assertEqual(3200, node.cpu_speed)

    def test_updates_memory_numa_nodes(self):
        expected_memory = int(16691519488 / 2 / 1024 / 1024)
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        process_lxd_results(
            node, make_lxd_output_json(SAMPLE_LXD_RESOURCES), 0
        )
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(2, len(numa_nodes))
        for numa_node in numa_nodes:
            self.assertEqual(expected_memory, numa_node.memory)
            [hugepages] = numa_node.hugepages_set.all()
            self.assertEqual(hugepages.page_size, 2097152)
            self.assertEqual(hugepages.total, 0)

    def test_updates_numa_node_hugepages(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}
        lxd_json = deepcopy(SAMPLE_LXD_RESOURCES)
        lxd_json["memory"]["nodes"][0]["hugepages_total"] = 16 * 2097152
        lxd_json["memory"]["nodes"][1]["hugepages_total"] = 8 * 2097152
        process_lxd_results(node, make_lxd_output_json(lxd_json), 0)
        numa_node1, numa_node2 = NUMANode.objects.filter(node=node).order_by(
            "index"
        )
        hugepages1 = numa_node1.hugepages_set.first()
        self.assertEqual(hugepages1.page_size, 2097152)
        self.assertEqual(hugepages1.total, 16 * 2097152)
        hugepages2 = numa_node2.hugepages_set.first()
        self.assertEqual(hugepages2.page_size, 2097152)
        self.assertEqual(hugepages2.total, 8 * 2097152)

    def test_no_update_numa_node_hugepages_if_commissioining(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}
        process_lxd_results(
            node, make_lxd_output_json(SAMPLE_LXD_RESOURCES), 0
        )
        for numa_node in NUMANode.objects.filter(node=node):
            self.assertFalse(numa_node.hugepages_set.exists())

    def test_updates_memory_numa_nodes_missing(self):
        total_memory = SAMPLE_LXD_RESOURCES_NO_NUMA["memory"]["total"]
        node = factory.make_Node()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        process_lxd_results(
            node, make_lxd_output_json(SAMPLE_LXD_RESOURCES_NO_NUMA), 0
        )
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(1, len(numa_nodes))
        for numa_node in numa_nodes:
            self.assertEqual(int(total_memory / 1024 / 1024), numa_node.memory)

    def test_updates_invalid_storage_devices(self):
        node = factory.make_Node()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        process_lxd_results(
            node, make_lxd_output_json(SAMPLE_LXD_RESOURCES_LP1906834), 0
        )
        node = reload_object(node)
        boot_disk = node.get_boot_disk()
        self.assertEqual(boot_disk.name, "sda")

    def test_accepts_numa_node_zero_memory(self):
        # Regression test for LP:1878923
        node = factory.make_Node()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}
        data = make_lxd_output()
        data["resources"]["memory"] = {
            "nodes": [
                {
                    "numa_node": 0,
                    "hugepages_used": 0,
                    "hugepages_total": 0,
                    "used": 1314131968,
                    "total": 33720463360,
                },
                {
                    "numa_node": 1,
                    "hugepages_used": 0,
                    "hugepages_total": 0,
                    "used": 0,
                    "total": 0,
                },
            ],
            "hugepages_total": 0,
            "hugepages_used": 0,
            "hugepages_size": 2097152,
            "used": 602902528,
            "total": 33720463360,
        }

        process_lxd_results(node, json.dumps(data).encode(), 0)

        self.assertEqual(32158, node.memory)
        self.assertCountEqual(
            [32158, 0], [numa.memory for numa in node.numanode_set.all()]
        )

    def test_updates_memory_no_corresponding_cpu_numa_node(self):
        # Regression test for LP:1885157
        node = factory.make_Node()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}
        data = make_lxd_output()
        data["resources"]["memory"] = {
            "nodes": [
                {
                    "numa_node": 252,
                    "hugepages_used": 0,
                    "hugepages_total": 0,
                    "used": 1314131968,
                    "total": 33720463360,
                },
                {
                    "numa_node": 253,
                    "hugepages_used": 0,
                    "hugepages_total": 0,
                    "used": 0,
                    "total": 0,
                },
                {
                    "numa_node": 254,
                    "hugepages_used": 0,
                    "hugepages_total": 0,
                    "used": 0,
                    "total": 0,
                },
                {
                    "numa_node": 255,
                    "hugepages_used": 0,
                    "hugepages_total": 0,
                    "used": 0,
                    "total": 0,
                },
            ],
            "hugepages_total": 0,
            "hugepages_used": 0,
            "hugepages_size": 2097152,
            "used": 602902528,
            "total": 33720463360,
        }

        process_lxd_results(node, json.dumps(data).encode(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(6, len(numa_nodes))

    def test_updates_cpu_numa_nodes(self):
        node = factory.make_Node()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        process_lxd_results(node, make_lxd_output_json(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual([0, 1, 2, 3], numa_nodes[0].cores)
        self.assertEqual([4, 5, 6, 7], numa_nodes[1].cores)

    def test_updates_cpu_numa_nodes_per_thread(self):
        node = factory.make_Node()
        self.patch(
            hooks_module, "update_node_network_information"
        ).return_value = {}

        lxd_json = deepcopy(SAMPLE_LXD_RESOURCES)
        cores_data = lxd_json["cpu"]["sockets"][0]["cores"]
        # each core has one thread in each numa node
        for core in cores_data:
            core["threads"][0]["numa_node"] = 0
            core["threads"][1]["numa_node"] = 1
        process_lxd_results(node, make_lxd_output_json(lxd_json), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual([0, 2, 4, 6], numa_nodes[0].cores)
        self.assertEqual([1, 3, 5, 7], numa_nodes[1].cores)

    def test_updates_network_numa_nodes(self):
        node = factory.make_Node()
        process_lxd_results(node, make_lxd_output_json(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        node_interfaces = list(
            Interface.objects.filter(node_config=node.current_config).order_by(
                "name"
            )
        )
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual(node_interfaces[0].numa_node, numa_nodes[0])
        self.assertEqual(node_interfaces[1].numa_node, numa_nodes[1])
        self.assertEqual(node_interfaces[2].numa_node, numa_nodes[0])

    def test_updates_storage_numa_nodes(self):
        node = factory.make_Node()
        process_lxd_results(node, make_lxd_output_json(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        node_interfaces = list(
            node.physicalblockdevice_set.all().order_by("name")
        )
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual(node_interfaces[0].numa_node, numa_nodes[0])
        self.assertEqual(node_interfaces[1].numa_node, numa_nodes[1])

    def test_creates_node_devices(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        usb_device = make_lxd_usb_device()
        pcie_device = make_lxd_pcie_device()
        lxd_output["resources"]["usb"] = {
            "devices": [usb_device],
            "total": 1,
        }
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        usb_node_device = node.current_config.nodedevice_set.get(
            bus=NODE_DEVICE_BUS.USB
        )
        pcie_node_device = node.current_config.nodedevice_set.get(
            bus=NODE_DEVICE_BUS.PCIE
        )

        self.assertEqual(2, node.current_config.nodedevice_set.count())

        self.assertEqual(usb_node_device.hardware_type, HARDWARE_TYPE.NODE)
        self.assertEqual(usb_node_device.vendor_id, usb_device["vendor_id"])
        self.assertEqual(usb_node_device.product_id, usb_device["product_id"])
        self.assertEqual(usb_node_device.vendor_name, usb_device["vendor"])
        self.assertEqual(usb_node_device.product_name, usb_device["product"])
        self.assertEqual(usb_node_device.bus_number, usb_device["bus_address"])
        self.assertEqual(
            usb_node_device.commissioning_driver,
            ", ".join(
                {interface["driver"] for interface in usb_device["interfaces"]}
            ),
        )
        self.assertEqual(
            usb_node_device.device_number, usb_device["device_address"]
        )
        self.assertIsNone(usb_node_device.pci_address)

        self.assertEqual(pcie_node_device.hardware_type, HARDWARE_TYPE.NODE)
        self.assertEqual(pcie_node_device.vendor_id, pcie_device["vendor_id"])
        self.assertEqual(
            pcie_node_device.product_id, pcie_device["product_id"]
        )
        self.assertEqual(pcie_node_device.vendor_name, pcie_device["vendor"])
        self.assertEqual(pcie_node_device.product_name, pcie_device["product"])
        self.assertEqual(
            pcie_node_device.commissioning_driver, pcie_device["driver"]
        )
        self.assertEqual(
            pcie_node_device.pci_address, pcie_device["pci_address"]
        )

    def test_creates_node_pci_device_vpd(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        pcie_device = make_lxd_pcie_device()
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        pcie_node_device = node.current_config.nodedevice_set.get(
            bus=NODE_DEVICE_BUS.PCIE
        )

        pcie_node_device_vpd = pcie_node_device.nodedevicevpd_set.all()

        self.assertCountEqual(
            list(pcie_device["vpd"]["entries"].items()),
            list(pcie_node_device_vpd.values_list("key", "value")),
        )

    def test_creates_node_pci_device_vpd_with_null_character(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        pcie_device = make_lxd_pcie_device()
        pcie_device["vpd"]["entries"] = {"YB": "abc\x00xyz"}
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        pcie_node_device = node.current_config.nodedevice_set.get(
            bus=NODE_DEVICE_BUS.PCIE
        )

        pcie_node_device_vpd = pcie_node_device.nodedevicevpd_set.get(
            node_device_id=pcie_node_device.id, key="YB"
        )

        self.assertEqual(
            "abc\\x00xyz",
            pcie_node_device_vpd.value,
        )

    def test_recreates_node_pci_device_vpd_during_recommission(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        pcie_device = make_lxd_pcie_device()
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        pcie_node_device = node.current_config.nodedevice_set.get(
            bus=NODE_DEVICE_BUS.PCIE
        )

        pcie_node_device_vpd = pcie_node_device.nodedevicevpd_set.all()

        self.assertCountEqual(
            list(pcie_device["vpd"]["entries"].items()),
            list(pcie_node_device_vpd.values_list("key", "value")),
        )

    def test_usb_device_null_interfaces(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        usb_device = make_lxd_usb_device()
        usb_device["interfaces"] = None
        lxd_output["resources"]["usb"] = {
            "devices": [usb_device],
            "total": 1,
        }
        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        usb_node_device = node.current_config.nodedevice_set.get(
            bus=NODE_DEVICE_BUS.USB
        )
        self.assertEqual(usb_node_device.hardware_type, HARDWARE_TYPE.NODE)
        self.assertEqual(usb_node_device.vendor_id, usb_device["vendor_id"])
        self.assertEqual(usb_node_device.product_id, usb_device["product_id"])
        self.assertEqual(usb_node_device.vendor_name, usb_device["vendor"])
        self.assertEqual(usb_node_device.product_name, usb_device["product"])
        self.assertEqual(usb_node_device.bus_number, usb_device["bus_address"])
        self.assertEqual(usb_node_device.commissioning_driver, "")
        self.assertEqual(
            usb_node_device.device_number, usb_device["device_address"]
        )
        self.assertIsNone(usb_node_device.pci_address)

    def test_updates_node_device(self):
        node = factory.make_Node()
        pcie_device = factory.make_NodeDevice(
            node=node, bus=NODE_DEVICE_BUS.PCIE
        )
        lxd_output = make_lxd_output()
        new_vendor_name = factory.make_name("vendor_name")
        new_product_name = factory.make_name("product_name")
        new_commissioning_driver = factory.make_name("commissioning_driver")
        lxd_output["resources"]["pci"] = {
            "devices": [
                {
                    "driver": new_commissioning_driver,
                    "numa_node": pcie_device.numa_node.index,
                    "pci_address": pcie_device.pci_address,
                    "product": new_product_name,
                    "product_id": pcie_device.product_id,
                    "vendor": new_vendor_name,
                    "vendor_id": pcie_device.vendor_id,
                }
            ],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        pcie_device = reload_object(pcie_device)

        self.assertEqual(new_vendor_name, pcie_device.vendor_name)
        self.assertEqual(new_product_name, pcie_device.product_name)
        self.assertEqual(
            new_commissioning_driver, pcie_device.commissioning_driver
        )

    def test_removes_node_devices(self):
        node = factory.make_Node()
        old_node_devices = [
            factory.make_NodeDevice(node=node) for _ in range(20)
        ]
        lxd_output = make_lxd_output()
        pcie_device = make_lxd_pcie_device()
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        pcie_node_device = node.current_config.nodedevice_set.first()

        self.assertEqual(1, node.current_config.nodedevice_set.count())
        self.assertEqual(pcie_node_device.vendor_id, pcie_device["vendor_id"])
        self.assertEqual(
            pcie_node_device.product_id, pcie_device["product_id"]
        )
        self.assertEqual(pcie_node_device.vendor_name, pcie_device["vendor"])
        self.assertEqual(pcie_node_device.product_name, pcie_device["product"])
        self.assertEqual(
            pcie_node_device.commissioning_driver, pcie_device["driver"]
        )
        self.assertEqual(
            pcie_node_device.pci_address, pcie_device["pci_address"]
        )
        for old_node_device in old_node_devices:
            self.assertIsNone(reload_object(old_node_device))

    def test_assoicates_node_device_with_physical_iface(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        pcie_device1 = make_lxd_pcie_device()
        pcie_device2 = make_lxd_pcie_device()
        usb_device = make_lxd_usb_device()
        lxd_output["resources"]["usb"] = {
            "devices": [usb_device],
            "total": 1,
        }
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device1, pcie_device2],
            "total": 2,
        }
        lxd_output["resources"]["network"]["cards"][0][
            "pci_address"
        ] = pcie_device1["pci_address"]
        lxd_output["resources"]["network"]["cards"][1][
            "pci_address"
        ] = pcie_device2["pci_address"]
        lxd_output["resources"]["network"]["cards"][2][
            "usb_address"
        ] = "{}:{}".format(
            usb_device["bus_address"], usb_device["device_address"]
        )
        del lxd_output["resources"]["network"]["cards"][2]["pci_address"]

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        for node_device in node.current_config.nodedevice_set.all():
            self.assertEqual(HARDWARE_TYPE.NETWORK, node_device.hardware_type)
            self.assertIsNotNone(node_device.physical_interface)

    def test_assoicates_node_device_with_physical_blockdevice(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        pcie_device = make_lxd_pcie_device()
        usb_device = make_lxd_usb_device()
        lxd_output["resources"]["usb"] = {
            "devices": [usb_device],
            "total": 1,
        }
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }
        lxd_output["resources"]["storage"]["disks"][0][
            "pci_address"
        ] = pcie_device["pci_address"]
        lxd_output["resources"]["storage"]["disks"][1][
            "usb_address"
        ] = "{}:{}".format(
            usb_device["bus_address"], usb_device["device_address"]
        )

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        for node_device in node.current_config.nodedevice_set.all():
            self.assertEqual(HARDWARE_TYPE.STORAGE, node_device.hardware_type)
            self.assertIsNotNone(node_device.physical_blockdevice)

    def test_creates_node_device_gpu(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        usb_device = make_lxd_usb_device()
        usb_device["usb_address"] = "{}:{}".format(
            usb_device["bus_address"],
            usb_device["device_address"],
        )
        pcie_device = make_lxd_pcie_device()
        lxd_output["resources"]["usb"] = {
            "devices": [usb_device],
            "total": 1,
        }
        lxd_output["resources"]["pci"] = {
            "devices": [pcie_device],
            "total": 1,
        }
        lxd_output["resources"]["gpu"] = {
            "cards": [usb_device, pcie_device],
            "total": 2,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        self.assertEqual(
            {
                NODE_DEVICE_BUS.USB: HARDWARE_TYPE.GPU,
                NODE_DEVICE_BUS.PCIE: HARDWARE_TYPE.GPU,
            },
            {
                node_device.bus: node_device.hardware_type
                for node_device in node.current_config.nodedevice_set.all()
            },
        )

    def test_allows_devices_on_sparse_numa_nodes(self):
        node = factory.make_Node()
        lxd_output = make_lxd_output()
        pci_address = lxd_output["resources"]["network"]["cards"][-1][
            "pci_address"
        ]
        lxd_output["resources"]["cpu"]["sockets"][-1]["cores"][-1]["threads"][
            -1
        ]["numa_node"] = 16
        lxd_output["resources"]["network"]["cards"][-1]["numa_node"] = 16
        lxd_output["resources"]["pci"] = {
            "devices": [
                make_lxd_pcie_device(numa_node=16, pci_address=pci_address)
            ],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)
        node_device = node.current_config.nodedevice_set.get(
            pci_address=pci_address
        )

        self.assertEqual(16, node_device.numa_node.index)
        self.assertEqual(16, node_device.physical_interface.numa_node.index)

    def test_replace_existing_device_pcie(self):
        node = factory.make_Node()
        old_node_device = factory.make_NodeDevice(
            node=node, bus=NODE_DEVICE_BUS.PCIE
        )
        pci_address = old_node_device.pci_address
        lxd_output = make_lxd_output()
        lxd_output["resources"]["pci"] = {
            "devices": [make_lxd_pcie_device(pci_address=pci_address)],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        self.assertIsNone(reload_object(old_node_device))
        self.assertIsNotNone(
            node.current_config.nodedevice_set.get(pci_address=pci_address)
        )

    def test_replace_existing_device_usb(self):
        node = factory.make_Node()
        old_node_device = factory.make_NodeDevice(
            node=node, bus=NODE_DEVICE_BUS.USB
        )
        bus_number = old_node_device.bus_number
        device_number = old_node_device.device_number
        lxd_output = make_lxd_output()
        lxd_output["resources"]["usb"] = {
            "devices": [
                make_lxd_usb_device(
                    bus_address=bus_number, device_address=device_number
                )
            ],
            "total": 1,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        self.assertIsNone(reload_object(old_node_device))
        self.assertIsNotNone(
            node.current_config.nodedevice_set.get(
                bus_number=bus_number, device_number=device_number
            )
        )

    def test_replace_existing_storage_device(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node, pcie=True)
        node_device = block_device.node_device
        lxd_output = make_lxd_output()
        lxd_output["resources"]["storage"]["disks"] = [
            {
                "id": block_device.name,
                "model": block_device.model,
                "type": "nvme",
                "read_only": False,
                "serial": block_device.serial,
                "size": block_device.size,
                "removable": False,
                "device_path": "pci-0000:01:00.0-nvme-1",
                "block_size": block_device.block_size,
                "firmware_version": block_device.firmware_version,
                "rpm": 0,
                "numa_node": block_device.numa_node.index,
            },
            {
                "id": factory.make_name("id"),
                "model": factory.make_name("model"),
                "type": "nvme",
                "read_only": False,
                "serial": factory.make_name("serial"),
                "size": block_device.size,
                "removable": False,
                "device_path": "pci-0000:02:00.0-nvme-1",
                "block_size": block_device.block_size,
                "firmware_version": factory.make_name("firmware_version"),
                "rpm": 0,
                "numa_node": block_device.numa_node.index,
            },
        ]
        lxd_output["resources"]["pci"] = {
            "devices": [
                {
                    "driver": node_device.commissioning_driver,
                    "numa_node": block_device.numa_node.index,
                    "pci_address": "0000:01:00.0",
                    "vendor": node_device.vendor_name,
                    "vendor_id": node_device.vendor_id,
                    "product": node_device.product_name,
                    "product_id": node_device.product_id,
                },
                {
                    "driver": factory.make_name("driver"),
                    "numa_node": block_device.numa_node.index,
                    "pci_address": "0000:02:00.0",
                    "vendor": factory.make_name("vendor_name"),
                    "vendor_id": factory.make_hex_string(size=4),
                    "product": factory.make_name("product_name"),
                    "product_id": factory.make_hex_string(size=4),
                },
            ],
            "total": 2,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        self.assertIsNone(reload_object(node_device))
        new_node_device = reload_object(block_device).node_device
        self.assertIsNotNone(new_node_device)
        self.assertEqual("0000:01:00.0", new_node_device.pci_address)

    def test_replace_existing_interface(self):
        node = factory.make_Node_with_Interface_on_Subnet()
        iface = reload_object(node.boot_interface)
        node_device = iface.node_device
        lxd_output = make_lxd_output()
        lxd_output["resources"]["network"]["cards"] = [
            {
                "ports": [
                    {
                        "id": iface.name,
                        "address": str(iface.mac_address),
                        "port": 0,
                        "protocol": "ethernet",
                        "link_detected": False,
                    }
                ],
                "numa_node": iface.numa_node.index,
                "pci_address": "0000:01:00.0",
                "vendor": iface.vendor,
                "product": iface.product,
                "firmware_version": iface.firmware_version,
            },
            {
                "ports": [
                    {
                        "id": factory.make_name("eth"),
                        "address": factory.make_mac_address(),
                        "port": 0,
                        "protocol": "ethernet",
                        "link_detected": False,
                    }
                ],
                "numa_node": iface.numa_node.index,
                "pci_address": "0000:02:00.0",
                "vendor": factory.make_name("vendor"),
                "product": factory.make_name("product"),
                "firmware_version": factory.make_name("firmware_version"),
            },
        ]
        lxd_output["networks"][iface.name] = {
            "hwaddr": str(iface.mac_address),
            "type": "broadcast",
            "addresses": [],
            "vlan": None,
            "bridge": None,
            "bond": None,
            "state": "up",
        }
        lxd_output["resources"]["pci"] = {
            "devices": [
                {
                    "driver": node_device.commissioning_driver,
                    "numa_node": iface.numa_node.index,
                    "pci_address": "0000:01:00.0",
                    "vendor": node_device.vendor_name,
                    "vendor_id": node_device.vendor_id,
                    "product": node_device.product_name,
                    "product_id": node_device.product_id,
                },
                {
                    "driver": factory.make_name("driver"),
                    "numa_node": iface.numa_node.index,
                    "pci_address": "0000:02:00.0",
                    "vendor": factory.make_name("vendor_name"),
                    "vendor_id": factory.make_hex_string(size=4),
                    "product": factory.make_name("product_name"),
                    "product_id": factory.make_hex_string(size=4),
                },
            ],
            "total": 2,
        }

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        self.assertIsNone(reload_object(node_device))
        iface = Interface.objects.get(
            node_config=node.current_config, name=iface.name
        )
        new_node_device = iface.node_device
        self.assertIsNotNone(new_node_device)
        self.assertEqual("0000:01:00.0", new_node_device.pci_address)

    def test_updates_interfaces_speed(self):
        node = factory.make_Node()
        iface = factory.make_Interface(
            node=node,
            mac_address="00:00:00:00:00:01",
            interface_speed=0,
            link_speed=0,
        )
        process_lxd_results(node, make_lxd_output_json(), 0)
        # the existing interface gets updated
        iface1 = reload_object(iface)
        self.assertEqual(1000, iface1.link_speed)
        self.assertEqual(1000, iface1.interface_speed)
        # other interfaces get created
        iface2, iface3 = (
            Interface.objects.filter(node_config=node.current_config)
            .exclude(mac_address=iface.mac_address)
            .order_by("mac_address")
        )
        self.assertEqual(0, iface2.link_speed)
        self.assertEqual(1000, iface2.interface_speed)
        self.assertEqual(0, iface3.link_speed)
        self.assertEqual(0, iface3.interface_speed)

    def test_ignores_system_information_placeholders(self):
        node = factory.make_Node()
        modified_sample_lxd_data = make_lxd_output()
        for k, v in modified_sample_lxd_data["resources"]["system"].items():
            if isinstance(v, dict):
                for x, w in v.items():
                    modified_sample_lxd_data["resources"]["system"][k][
                        x
                    ] = random.choice([None, "0123456789", "none"])
            else:
                modified_sample_lxd_data["resources"]["system"][
                    k
                ] = random.choice([None, "0123456789", "none"])
        process_lxd_results(
            node, json.dumps(modified_sample_lxd_data).encode(), 0
        )
        self.assertFalse(
            node.nodemetadata_set.exclude(key="cpu_model").exists()
        )

    def test_handles_none_system_information(self):
        # Regression test for LP:1881116
        node = factory.make_Node()
        modified_sample_lxd_data = make_lxd_output()
        for key in ["motherboard", "firmware", "chassis"]:
            modified_sample_lxd_data["resources"]["system"][key] = None
        process_lxd_results(
            node, json.dumps(modified_sample_lxd_data).encode(), 0
        )
        self.assertEqual(
            0,
            node.nodemetadata_set.filter(
                Q(key__startswith="mainboard")
                | Q(key__startswith="firmware")
                | Q(key__startswith="chassis")
            ).count(),
        )

    def test_removes_missing_nodemetadata(self):
        node = factory.make_Node()
        process_lxd_results(node, make_lxd_output_json(), 0)
        self.assertTrue(
            node.nodemetadata_set.exclude(key="cpu_model").exists()
        )
        modified_sample_lxd_data = make_lxd_output()
        del modified_sample_lxd_data["resources"]["system"]
        process_lxd_results(
            node, json.dumps(modified_sample_lxd_data).encode(), 0
        )
        self.assertFalse(
            node.nodemetadata_set.exclude(key="cpu_model").exists()
        )

    def test_removes_virtual_tag(self):
        node = factory.make_Node()
        tag, _ = Tag.objects.get_or_create(name="virtual")
        node.tags.add(tag)
        process_lxd_results(
            node, make_lxd_output_json(virt_type="physical"), 0
        )
        self.assertFalse(node.tags.filter(name="virtual").exists())

    def test_syncs_pods(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        pod.hints.nodes.add(node)
        process_lxd_results(node, make_lxd_output_json(), 0)
        pod.hints.refresh_from_db()

        self.assertEqual(8, pod.hints.cores)
        self.assertEqual(2400, pod.hints.cpu_speed)
        self.assertEqual(15918, pod.hints.memory)

    def test_link_nodes_with_dpu(self):
        pci_device_vpd = LXDPCIDeviceVPD(entries={"SN": factory.make_string()})

        host = factory.make_Node()
        host_data = FakeCommissioningData()
        host_pci_addr = host_data.allocate_pci_address()
        host_card = LXDNetworkCard(pci_address=host_pci_addr)
        host_data.create_pci_device(
            host_pci_addr,
            "15b3",
            host_card.vendor,
            host_card.product_id,
            host_card.product,
            host_card.driver,
            host_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(host, json.dumps(host_data.render()).encode(), 0)

        dpu = factory.make_Node()
        dpu_data = FakeCommissioningData()
        dpu_data.create_system_resource("BlueField")
        dpu_pci_addr = dpu_data.allocate_pci_address()
        dpu_card = LXDNetworkCard(pci_address=dpu_pci_addr)
        dpu_data.create_pci_device(
            dpu_pci_addr,
            "15b3",
            dpu_card.vendor,
            dpu_card.product_id,
            dpu_card.product,
            dpu_card.driver,
            dpu_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(dpu, json.dumps(dpu_data.render()).encode(), 0)

        self.assertEqual(dpu.parent_id, host.id)

    def test_link_nodes_with_multiple_dpu(self):
        pci_device_vpd = LXDPCIDeviceVPD(entries={"SN": factory.make_string()})

        host = factory.make_Node()
        host_data = FakeCommissioningData()
        host_pci_addr = host_data.allocate_pci_address()
        host_card = LXDNetworkCard(pci_address=host_pci_addr)
        host_data.create_pci_device(
            host_pci_addr,
            "15b3",
            host_card.vendor,
            host_card.product_id,
            host_card.product,
            host_card.driver,
            host_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(host, json.dumps(host_data.render()).encode(), 0)

        dpu1 = factory.make_Node()
        dpu1_data = FakeCommissioningData()
        dpu1_data.create_system_resource("BlueField")
        dpu1_pci_addr = dpu1_data.allocate_pci_address()
        dpu1_card = LXDNetworkCard(pci_address=dpu1_pci_addr)
        dpu1_data.create_pci_device(
            dpu1_pci_addr,
            "15b3",
            dpu1_card.vendor,
            dpu1_card.product_id,
            dpu1_card.product,
            dpu1_card.driver,
            dpu1_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(dpu1, json.dumps(dpu1_data.render()).encode(), 0)

        dpu2 = factory.make_Node()
        dpu2_data = FakeCommissioningData()
        dpu2_data.create_system_resource("BlueField")
        dpu2_pci_addr = dpu2_data.allocate_pci_address()
        dpu2_card = LXDNetworkCard(pci_address=dpu2_pci_addr)
        dpu2_data.create_pci_device(
            dpu2_pci_addr,
            "15b3",
            dpu2_card.vendor,
            dpu2_card.product_id,
            dpu2_card.product,
            dpu2_card.driver,
            dpu2_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(dpu2, json.dumps(dpu2_data.render()).encode(), 0)

        self.assertEqual(dpu1.parent_id, host.id)
        self.assertEqual(dpu2.parent_id, host.id)

    def test_do_not_link_dpu_if_vendor_missmatch(self):
        pci_device_vpd = LXDPCIDeviceVPD(entries={"SN": factory.make_string()})

        host = factory.make_Node()
        host_data = FakeCommissioningData()
        host_pci_addr = host_data.allocate_pci_address()
        host_card = LXDNetworkCard(pci_address=host_pci_addr)
        host_data.create_pci_device(
            host_pci_addr,
            "",
            host_card.vendor,
            host_card.product_id,
            host_card.product,
            host_card.driver,
            host_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(host, json.dumps(host_data.render()).encode(), 0)

        dpu = factory.make_Node()
        dpu_data = FakeCommissioningData()
        dpu_data.create_system_resource("BlueField")
        dpu_pci_addr = dpu_data.allocate_pci_address()
        dpu_card = LXDNetworkCard(pci_address=dpu_pci_addr)
        dpu_data.create_pci_device(
            dpu_pci_addr,
            "15b3",
            dpu_card.vendor,
            dpu_card.product_id,
            dpu_card.product,
            dpu_card.driver,
            dpu_card.driver_version,
            pci_device_vpd,
        )
        process_lxd_results(dpu, json.dumps(dpu_data.render()).encode(), 0)

        self.assertIsNone(dpu.parent_id)

    def test_do_not_link_dpu_if_sn_missmatch(self):
        host_pci_device_vpd = LXDPCIDeviceVPD(
            entries={"SN": factory.make_string()}
        )
        host = factory.make_Node()
        host_data = FakeCommissioningData()
        host_pci_addr = host_data.allocate_pci_address()
        host_card = LXDNetworkCard(pci_address=host_pci_addr)
        host_data.create_pci_device(
            host_pci_addr,
            "15b3",
            host_card.vendor,
            host_card.product_id,
            host_card.product,
            host_card.driver,
            host_card.driver_version,
            host_pci_device_vpd,
        )
        process_lxd_results(host, json.dumps(host_data.render()).encode(), 0)

        dpu_pci_device_vpd = LXDPCIDeviceVPD(
            entries={"SN": factory.make_string()}
        )
        dpu = factory.make_Node()
        dpu_data = FakeCommissioningData()
        dpu_data.create_system_resource("BlueField")
        dpu_pci_addr = dpu_data.allocate_pci_address()
        dpu_card = LXDNetworkCard(pci_address=dpu_pci_addr)
        dpu_data.create_pci_device(
            dpu_pci_addr,
            "15b3",
            dpu_card.vendor,
            dpu_card.product_id,
            dpu_card.product,
            dpu_card.driver,
            dpu_card.driver_version,
            dpu_pci_device_vpd,
        )
        process_lxd_results(dpu, json.dumps(dpu_data.render()).encode(), 0)

        self.assertIsNone(dpu.parent_id)

    def test_do_not_link_dpu_if_no_product_and_sn_match(self):
        host1_pci_device_vpd = LXDPCIDeviceVPD(
            entries={"SN": factory.make_string()}
        )
        host1 = factory.make_Node()
        host1_data = FakeCommissioningData()
        host1_pci_addr = host1_data.allocate_pci_address()
        host1_card = LXDNetworkCard(
            pci_address=host1_pci_addr, product_id="1234"
        )
        host1_data.create_pci_device(
            host1_pci_addr,
            "15b3",
            host1_card.vendor,
            host1_card.product_id,
            host1_card.product,
            host1_card.driver,
            host1_card.driver_version,
            host1_pci_device_vpd,
        )
        process_lxd_results(host1, json.dumps(host1_data.render()).encode(), 0)

        host2_pci_device_vpd = LXDPCIDeviceVPD(
            entries={"SN": factory.make_string()}
        )
        host2 = factory.make_Node()
        host2_data = FakeCommissioningData()
        host2_pci_addr = host2_data.allocate_pci_address()
        host2_card = LXDNetworkCard(
            pci_address=host2_pci_addr, product_id="5678"
        )
        host2_data.create_pci_device(
            host2_pci_addr,
            "15b3",
            host2_card.vendor,
            host2_card.product_id,
            host2_card.product,
            host2_card.driver,
            host2_card.driver_version,
            host2_pci_device_vpd,
        )
        process_lxd_results(host2, json.dumps(host2_data.render()).encode(), 0)

        dpu = factory.make_Node()
        dpu_data = FakeCommissioningData()
        dpu_data.create_system_resource("BlueField")
        dpu_pci_addr = dpu_data.allocate_pci_address()
        dpu_card = LXDNetworkCard(
            pci_address=dpu_pci_addr, product_id=host1_card.product_id
        )
        dpu_data.create_pci_device(
            dpu_pci_addr,
            "15b3",
            dpu_card.vendor,
            dpu_card.product_id,
            dpu_card.product,
            dpu_card.driver,
            dpu_card.driver_version,
            host2_pci_device_vpd,
        )
        process_lxd_results(dpu, json.dumps(dpu_data.render()).encode(), 0)

        self.assertIsNone(dpu.parent_id)

    def test_link_parent_only_to_matching_node(self):
        machine_pci_device_vpd = LXDPCIDeviceVPD(
            entries={"SN": factory.make_string()}
        )
        machine = factory.make_Node()
        machine_data = FakeCommissioningData()
        machine_pci_addr = machine_data.allocate_pci_address()
        machine_card = LXDNetworkCard(pci_address=machine_pci_addr)
        machine_data.create_pci_device(
            machine_pci_addr,
            "",
            machine_card.vendor,
            machine_card.product_id,
            machine_card.product,
            machine_card.driver,
            machine_card.driver_version,
            machine_pci_device_vpd,
        )
        process_lxd_results(
            machine, json.dumps(machine_data.render()).encode(), 0
        )

        host_pci_device_vpd = LXDPCIDeviceVPD(
            entries={"SN": factory.make_string()}
        )
        host = factory.make_Node()
        host_data = FakeCommissioningData()
        host_pci_addr = host_data.allocate_pci_address()
        host_card = LXDNetworkCard(pci_address=host_pci_addr)

        dpu = factory.make_Node()
        dpu_data = FakeCommissioningData()
        dpu_data.create_system_resource("BlueField")
        dpu_pci_addr = dpu_data.allocate_pci_address()
        dpu_card = LXDNetworkCard(
            pci_address=dpu_pci_addr, product_id=host_card.product_id
        )
        dpu_data.create_pci_device(
            dpu_pci_addr,
            "15b3",
            dpu_card.vendor,
            dpu_card.product_id,
            dpu_card.product,
            dpu_card.driver,
            dpu_card.driver_version,
            host_pci_device_vpd,
        )
        process_lxd_results(dpu, json.dumps(dpu_data.render()).encode(), 0)

        host_data.create_pci_device(
            host_pci_addr,
            "15b3",
            host_card.vendor,
            host_card.product_id,
            host_card.product,
            host_card.driver,
            host_card.driver_version,
            host_pci_device_vpd,
        )
        process_lxd_results(host, json.dumps(host_data.render()).encode(), 0)

        machine = Node.objects.get(id=machine.id)
        self.assertIsNone(machine.parent)

        dpu = Node.objects.get(id=dpu.id)
        self.assertEqual(host.id, dpu.parent_id)


class TestUpdateNodePhysicalBlockDevices(MAASServerTestCase):
    def test_idempotent_block_devices(self):
        device_names = [
            device["id"] for device in SAMPLE_LXD_RESOURCES["storage"]["disks"]
        ]
        node = factory.make_Node()
        numa_nodes = create_numa_nodes(node)
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, numa_nodes
        )
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, numa_nodes
        )
        devices = list(node.physicalblockdevice_set.all())
        created_names = []
        for index, device in enumerate(devices):
            created_names.append(device.name)
            self.assertEqual(device.numa_node, numa_nodes[index])
        self.assertCountEqual(device_names, created_names)

    def test_does_nothing_if_skip_storage(self):
        node = factory.make_Node(skip_storage=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        _update_node_physical_block_devices(node, {}, create_numa_nodes(node))
        self.assertIsNotNone(reload_object(block_device))
        self.assertFalse(reload_object(node).skip_storage)

    def test_removes_previous_physical_block_devices(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        _update_node_physical_block_devices(node, {}, create_numa_nodes(node))
        self.assertIsNone(reload_object(block_device))

    def test_creates_physical_block_devices(self):
        device_names = [
            device["id"] for device in SAMPLE_LXD_RESOURCES["storage"]["disks"]
        ]
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_names = [
            device.name for device in node.physicalblockdevice_set.all()
        ]
        self.assertCountEqual(device_names, created_names)

    def test_skips_read_only_and_cdroms(self):
        node = factory.make_Node()
        READ_ONLY_AND_CDROM = deepcopy(SAMPLE_LXD_RESOURCES)
        READ_ONLY_AND_CDROM["storage"]["disks"][0]["read_only"] = "true"
        READ_ONLY_AND_CDROM["storage"]["disks"][1]["type"] = "cdrom"
        _update_node_physical_block_devices(
            node, READ_ONLY_AND_CDROM, create_numa_nodes(node)
        )
        created_names = [
            device.name for device in node.physicalblockdevice_set.all()
        ]
        self.assertCountEqual([], created_names)

    def test_handles_renamed_block_device(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        NEW_NAMES = deepcopy(SAMPLE_LXD_RESOURCES)
        NEW_NAMES["storage"]["disks"][0]["id"] = "sdy"
        NEW_NAMES["storage"]["disks"][1]["id"] = "sdz"
        _update_node_physical_block_devices(
            node, NEW_NAMES, create_numa_nodes(node)
        )
        device_names = ["sdy", "sdz"]
        created_names = [
            device.name for device in node.physicalblockdevice_set.all()
        ]
        self.assertCountEqual(device_names, created_names)

    def test_handles_new_block_device_in_front(self):
        # First simulate a node being commissioned with two disks. For
        # this test, there need to be at least two disks in order to
        # simulate a condition like the one in bug #1662343.
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        # Now, we simulate that we insert a new disk in the machine that
        # becomes sdx, thus pushing the other disks to sdy and sdz.
        NEW_NAMES = deepcopy(SAMPLE_LXD_RESOURCES)
        NEW_NAMES["storage"]["disks"][0]["id"] = "sdx"
        NEW_NAMES["storage"]["disks"][1]["id"] = "sdy"
        NEW_NAMES["storage"]["disks"].append(
            {
                "id": "sdz",
                "device": "8:0",
                "model": "Crucial_CT512M55",
                "type": "sata",
                "read_only": False,
                "size": 512110190789,
                "removable": False,
                "numa_node": 0,
                "device_path": "",
                "block_size": 4096,
                "rpm": 0,
                "firmware_version": "MU01",
                "serial": "14060968BC12",
            }
        )

        # After recommissioning the node, we'll have three devices, as
        # expected.
        _update_node_physical_block_devices(
            node, NEW_NAMES, create_numa_nodes(node)
        )
        device_names = [
            (device.name, device.serial)
            for device in node.physicalblockdevice_set.all()
        ]
        self.assertCountEqual(
            [
                ("sdx", NEW_NAMES["storage"]["disks"][0]["serial"]),
                ("sdy", NEW_NAMES["storage"]["disks"][1]["serial"]),
                ("sdz", NEW_NAMES["storage"]["disks"][2]["serial"]),
            ],
            device_names,
        )

    def test_only_updates_physical_block_devices(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_ids_one = [
            device.id for device in node.physicalblockdevice_set.all()
        ]
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_ids_two = [
            device.id for device in node.physicalblockdevice_set.all()
        ]
        self.assertCountEqual(created_ids_two, created_ids_one)

    def test_doesnt_reset_boot_disk(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        boot_disk = node.physicalblockdevice_set.first()
        node.boot_disk = boot_disk
        node.save()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertEqual(boot_disk, reload_object(node).boot_disk)

    def test_clears_boot_disk(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        _update_node_physical_block_devices(node, {}, create_numa_nodes(node))
        self.assertIsNone(reload_object(node).boot_disk)

    def test_creates_physical_block_devices_in_order(self):
        device_names = [
            device["id"] for device in SAMPLE_LXD_RESOURCES["storage"]["disks"]
        ]
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_names = [
            device.name
            for device in (node.physicalblockdevice_set.all().order_by("id"))
        ]
        self.assertEqual(device_names, created_names)

    def test_creates_physical_block_device(self):
        # Check first device from SAMPLE_LXD_RESOURCES
        device = SAMPLE_LXD_RESOURCES["storage"]["disks"][0]
        name = device["id"]
        id_path = f"/dev/disk/by-id/{device['device_id']}"
        size = device["size"]
        block_size = device["block_size"]
        model = device["model"]
        serial = device["serial"]
        firmware_version = device["firmware_version"]
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertThat(
            node.physicalblockdevice_set.first(),
            MatchesStructure.byEquality(
                name=name,
                id_path=id_path,
                size=size,
                block_size=block_size,
                model=model,
                serial=serial,
                firmware_version=firmware_version,
            ),
        )

    def test_creates_physical_block_device_with_default_block_size(self):
        SAMPLE_LXD_DEFAULT_BLOCK_SIZE = deepcopy(SAMPLE_LXD_RESOURCES)
        # Set block_size to zero.
        SAMPLE_LXD_DEFAULT_BLOCK_SIZE["storage"]["disks"][0]["block_size"] = 0
        device = SAMPLE_LXD_DEFAULT_BLOCK_SIZE["storage"]["disks"][0]
        name = device["id"]
        id_path = f"/dev/disk/by-id/{device['device_id']}"
        size = device["size"]
        block_size = 512
        model = device["model"]
        serial = device["serial"]
        firmware_version = device["firmware_version"]
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_DEFAULT_BLOCK_SIZE, create_numa_nodes(node)
        )
        self.assertThat(
            node.physicalblockdevice_set.first(),
            MatchesStructure.byEquality(
                name=name,
                id_path=id_path,
                size=size,
                block_size=block_size,
                model=model,
                serial=serial,
                firmware_version=firmware_version,
            ),
        )

    def test_creates_physical_block_device_with_path(self):
        NO_DEVICE_PATH = deepcopy(SAMPLE_LXD_RESOURCES)
        NO_DEVICE_PATH["storage"]["disks"][0]["device_id"] = ""
        device = NO_DEVICE_PATH["storage"]["disks"][0]
        name = device["id"]
        size = device["size"]
        block_size = device["block_size"]
        model = device["model"]
        serial = device["serial"]
        firmware_version = device["firmware_version"]
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, NO_DEVICE_PATH, create_numa_nodes(node)
        )
        self.assertThat(
            node.physicalblockdevice_set.first(),
            MatchesStructure.byEquality(
                name=name,
                id_path="/dev/%s" % name,
                size=size,
                block_size=block_size,
                model=model,
                serial=serial,
                firmware_version=firmware_version,
            ),
        )

    def test_creates_physical_block_device_with_path_for_missing_serial(self):
        NO_SERIAL = deepcopy(SAMPLE_LXD_RESOURCES)
        NO_SERIAL["storage"]["disks"][0]["serial"] = ""
        device = NO_SERIAL["storage"]["disks"][0]
        name = device["id"]
        size = device["size"]
        block_size = device["block_size"]
        model = device["model"]
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, NO_SERIAL, create_numa_nodes(node)
        )
        self.assertThat(
            node.physicalblockdevice_set.first(),
            MatchesStructure.byEquality(
                name=name,
                id_path="/dev/%s" % name,
                size=size,
                block_size=block_size,
                model=model,
                serial="",
            ),
        )

    def test_creates_physical_block_device_only_for_node(self):
        node = factory.make_Node(with_boot_disk=False)
        other_node = factory.make_Node(with_boot_disk=False)
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertEqual(
            0,
            other_node.physicalblockdevice_set.count(),
            "Created physical block device for the incorrect node.",
        )

    def test_creates_physical_block_device_with_rotary_tag(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.last()
        self.assertIn("rotary", device.tags)
        self.assertNotIn("ssd", device.tags)

    def test_creates_physical_block_device_with_rotary_and_rpm_tags(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.last()
        self.assertIn("rotary", device.tags)
        self.assertIn("5400rpm", device.tags)

    def test_creates_physical_block_device_with_ssd_tag(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.first()
        self.assertIn("ssd", device.tags)
        self.assertNotIn("rotary", device.tags)

    def test_creates_physical_block_device_without_removable_tag(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.first()
        self.assertNotIn("removable", device.tags)

    def test_creates_physical_block_device_with_removable_tag(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.last()
        self.assertIn("removable", device.tags)

    def test_creates_physical_block_device_without_sata_tag(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.last()
        self.assertNotIn("sata", device.tags)

    def test_creates_physical_block_device_with_sata_tag(self):
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        device = node.physicalblockdevice_set.first()
        self.assertIn("sata", device.tags)

    def test_ignores_min_block_device_size_devices(self):
        UNDER_MIN_BLOCK_SIZE = deepcopy(SAMPLE_LXD_RESOURCES)
        UNDER_MIN_BLOCK_SIZE["storage"]["disks"][0]["size"] = random.randint(
            1, MIN_BLOCK_DEVICE_SIZE
        )
        UNDER_MIN_BLOCK_SIZE["storage"]["disks"][1]["size"] = random.randint(
            1, MIN_BLOCK_DEVICE_SIZE
        )
        node = factory.make_Node()
        _update_node_physical_block_devices(
            node, UNDER_MIN_BLOCK_SIZE, create_numa_nodes(node)
        )
        self.assertFalse(node.physicalblockdevice_set.exists())

    def test_regenerates_testing_script_set(self):
        node = factory.make_Node()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        node.current_testing_script_set = (
            ScriptSet.objects.create_testing_script_set(
                node=node, scripts=[script.name]
            )
        )
        node.save()

        ONE_DISK = deepcopy(SAMPLE_LXD_RESOURCES)
        del ONE_DISK["storage"]["disks"][1]
        device = ONE_DISK["storage"]["disks"][0]
        _update_node_physical_block_devices(
            node, ONE_DISK, create_numa_nodes(node)
        )

        self.assertEqual(1, len(node.get_latest_testing_script_results))
        script_result = node.get_latest_testing_script_results.get(
            script=script
        )
        self.assertDictEqual(
            {
                "storage": {
                    "type": "storage",
                    "value": {
                        "id": node.physicalblockdevice_set.first().id,
                        "id_path": "/dev/disk/by-id/wwn-0x12345",
                        "name": device["id"],
                        "serial": device["serial"],
                        "model": device["model"],
                    },
                }
            },
            script_result.parameters,
        )

    def test_sets_default_configuration(self):
        node = factory.make_Node()

        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        # replace the cached object since the node is updated earlier
        node.current_config.node = node

        _, layout = get_applied_storage_layout_for_node(node)
        self.assertEqual(
            Config.objects.get_config("default_storage_layout"), layout
        )

    def test_applies_custom_layout(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        custom_storage_config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "500M",
                            "fs": "vfat",
                        },
                    ],
                },
            },
            "mounts": {
                "/boot/efi": {
                    "device": "sda1",
                }
            },
        }
        _update_node_physical_block_devices(
            node,
            SAMPLE_LXD_RESOURCES,
            create_numa_nodes(node),
            custom_storage_config=custom_storage_config,
        )
        sda = node.physicalblockdevice_set.get(name="sda")
        ptable = sda.get_partitiontable()
        self.assertEqual(ptable.table_type, PARTITION_TABLE_TYPE.GPT)
        [part] = ptable.partitions.all()
        fs = part.get_effective_filesystem()
        self.assertEqual(fs.fstype, FILESYSTEM_TYPE.VFAT)
        self.assertEqual(fs.mount_point, "/boot/efi")

    def test_no_layout_if_applies_custom_layout_fails_missing_disk(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        custom_storage_config = {
            "layout": {
                "vda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "vda1",
                            "size": "500M",
                            "fs": "vfat",
                        },
                    ],
                },
            },
            "mounts": {
                "/boot/efi": {
                    "device": "vda1",
                },
            },
        }
        _update_node_physical_block_devices(
            node,
            SAMPLE_LXD_RESOURCES,
            create_numa_nodes(node),
            custom_storage_config=custom_storage_config,
        )
        self.assertIsNone(
            node.physicalblockdevice_set.filter(name="vda").first()
        )
        [event] = Event.objects.all()
        self.assertEqual(event.node, node)
        self.assertEqual(event.type.name, EVENT_TYPES.CONFIGURING_STORAGE)
        self.assertEqual(
            event.description,
            "Cannot apply custom layout: Unknown machine disk(s): vda",
        )

    def test_no_layout_if_applies_custom_layout_fails_applying(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        custom_storage_config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "5T",
                            "fs": "ext4",
                        },
                    ],
                },
            },
            "mounts": {},
        }
        _update_node_physical_block_devices(
            node,
            SAMPLE_LXD_RESOURCES,
            create_numa_nodes(node),
            custom_storage_config=custom_storage_config,
        )
        sda = node.physicalblockdevice_set.get(name="sda")
        # no layout is applied
        self.assertIsNone(sda.get_partitiontable())
        [event] = Event.objects.all()
        self.assertEqual(event.node, node)
        self.assertEqual(event.type.name, EVENT_TYPES.CONFIGURING_STORAGE)
        self.assertEqual(
            event.description,
            "Cannot apply custom layout: "
            "{'size': ['Partition cannot be saved; not enough free space on the block device.']}",
        )

    def test_doesnt_set_storage_layout_if_deployed(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        mock_set_default_storage_layout = self.patch(
            node_module.Node, "set_default_storage_layout"
        )

        _update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        self.assertThat(mock_set_default_storage_layout, MockNotCalled())
        _, layout = get_applied_storage_layout_for_node(node)
        self.assertEqual("blank", layout)

    def test_condenses_luns(self):
        node = factory.make_Node()
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

        _update_node_physical_block_devices(
            node, resources, create_numa_nodes(node)
        )

        self.assertEqual(2, node.physicalblockdevice_set.count())
        sda = node.physicalblockdevice_set.get(name="sda")
        self.assertEqual(
            {
                "model": lun1_model,
                "serial": lun1_serial,
                "id_path": "/dev/disk/by-id/scsi-LUN1",
                "size": lun1_size,
                "block_size": lun1_block_size,
                "firmware_version": lun1_firmware_version,
                "tags": ["multipath"],
            },
            {
                "model": sda.model,
                "serial": sda.serial,
                "id_path": sda.id_path,
                "size": sda.size,
                "block_size": sda.block_size,
                "firmware_version": sda.firmware_version,
                "tags": sda.tags,
            },
        )
        sdb = node.physicalblockdevice_set.get(name="sdb")
        self.assertEqual(
            {
                "model": lun2_model,
                "serial": lun2_serial,
                "id_path": "/dev/disk/by-id/scsi-LUN2",
                "size": lun2_size,
                "block_size": lun2_block_size,
                "firmware_version": lun2_firmware_version,
                "tags": ["multipath"],
            },
            {
                "model": sdb.model,
                "serial": sdb.serial,
                "id_path": sdb.id_path,
                "size": sdb.size,
                "block_size": sdb.block_size,
                "firmware_version": sdb.firmware_version,
                "tags": sdb.tags,
            },
        )

    def test_condenses_luns_jbod(self):
        node = factory.make_Node()
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

        _update_node_physical_block_devices(
            node, resources, create_numa_nodes(node)
        )

        self.assertEqual(2, node.physicalblockdevice_set.count())
        sda = node.physicalblockdevice_set.get(name="sda")
        self.assertEqual(
            {
                "model": lun1_model,
                "serial": lun1_serial,
                "id_path": "/dev/disk/by-id/scsi-LUN1",
                "size": lun1_size,
                "block_size": lun1_block_size,
                "firmware_version": lun1_firmware_version,
                "tags": ["multipath"],
            },
            {
                "model": sda.model,
                "serial": sda.serial,
                "id_path": sda.id_path,
                "size": sda.size,
                "block_size": sda.block_size,
                "firmware_version": sda.firmware_version,
                "tags": sda.tags,
            },
        )
        sdb = node.physicalblockdevice_set.get(name="sdb")
        self.assertEqual(
            {
                "model": lun2_model,
                "serial": lun2_serial,
                "id_path": "/dev/disk/by-id/scsi-LUN2",
                "size": lun2_size,
                "block_size": lun2_block_size,
                "firmware_version": lun2_firmware_version,
                "tags": ["multipath"],
            },
            {
                "model": sdb.model,
                "serial": sdb.serial,
                "id_path": sdb.id_path,
                "size": sdb.size,
                "block_size": sdb.block_size,
                "firmware_version": sdb.firmware_version,
                "tags": sdb.tags,
            },
        )

    def test_no_condense_luns_different_serial(self):
        node = factory.make_Node()
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        resources["storage"]["disks"] = [
            {
                "id": "sda",
                "device": "8:0",
                "model": factory.make_name("model"),
                "type": "scsi",
                "read_only": False,
                "size": 1024**3 * 10,
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
                "size": 1024**3 * 10,
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

        _update_node_physical_block_devices(
            node, resources, create_numa_nodes(node)
        )

        self.assertCountEqual(
            node.physicalblockdevice_set.values_list("name", flat=True),
            ["sda", "sdb"],
        )

    def test_no_condense_luns_empty_serial(self):
        node = factory.make_Node()
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        resources["storage"]["disks"] = [
            {
                "id": "sda",
                "device": "8:0",
                "model": factory.make_name("model"),
                "type": "scsi",
                "read_only": False,
                "size": 1024**3 * 10,
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
                "size": 1024**3 * 10,
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

        _update_node_physical_block_devices(
            node, resources, create_numa_nodes(node)
        )

        self.assertCountEqual(
            node.physicalblockdevice_set.values_list("name", flat=True),
            ["sda", "sdb"],
        )

    def test_no_condense_luns_no_serial(self):
        node = factory.make_Node()
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

        _update_node_physical_block_devices(
            node, resources, create_numa_nodes(node)
        )

        # sr9 is not included because it's a cdrom
        self.assertCountEqual(
            node.physicalblockdevice_set.values_list("name", flat=True),
            ["sde"],
        )


class TestUpdateNodeNetworkInformation(MAASServerTestCase):
    """Tests the update_node_network_information function using data from LXD.

    The EXPECTED_MACS dictionary below must match the contents of the file,
    which should specify a list of physical interfaces (such as what would
    be expected to be found during commissioning).
    """

    EXPECTED_INTERFACES = {
        "eth0": "00:00:00:00:00:01",
        "eth1": "00:00:00:00:00:02",
        "eth2": "00:00:00:00:00:03",
    }

    def assert_expected_interfaces_and_macs_exist_for_node(
        self, node, expected_interfaces=EXPECTED_INTERFACES
    ):
        """Asserts to ensure that the type, name, and MAC address are
        appropriate, given Node's interfaces. (and an optional list of
        expected interfaces which must exist)
        """
        node_interfaces = list(
            Interface.objects.filter(node_config=node.current_config)
        )

        expected_interfaces = expected_interfaces.copy()

        self.assertEqual(len(expected_interfaces), len(node_interfaces))

        for interface in node_interfaces:
            if interface.name.startswith("eth") or interface.name.startswith(
                "ens"
            ):
                parts = interface.name.split(".")
                if len(parts) == 2 and parts[1].isdigit():
                    iftype = INTERFACE_TYPE.VLAN
                else:
                    iftype = INTERFACE_TYPE.PHYSICAL
                self.assertEqual(iftype, interface.type)
            self.assertIn(interface.name, expected_interfaces)
            self.assertEqual(
                expected_interfaces[interface.name],
                interface.mac_address,
            )

    def test_does_nothing_if_skip_networking(self):
        node = factory.make_Node(interface=True, skip_networking=True)
        boot_interface = node.get_boot_interface()
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        self.assertIsNotNone(reload_object(boot_interface))
        self.assertFalse(reload_object(node).skip_networking)

    def test_add_all_interfaces(self):
        """Test a node that has no previously known interfaces on which we
        need to add a series of interfaces.
        """
        node = factory.make_Node()
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_interfaces_for_all_ports(self):
        """Interfaces are created for all ports in a network card."""
        node = factory.make_Node()
        # all ports belong to a single card
        lxd_output = make_lxd_output()
        cards = lxd_output["resources"]["network"]["cards"]
        port1 = cards[1]["ports"][0]
        port2 = cards[2]["ports"][0]
        port1["port"] = 1
        port2["port"] = 2
        cards[0]["ports"].extend([port1, port2])
        # remove other cards
        del cards[1:]

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()
        update_node_network_information(
            node, lxd_output, create_numa_nodes(node)
        )

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_adds_vendor_info(self):
        """Vendor, product and firmware version details are added."""
        node = factory.make_Node()
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        nic = Interface.objects.get(mac_address="00:00:00:00:00:01")
        self.assertEqual(nic.vendor, "Intel Corporation")
        self.assertEqual(nic.product, "Ethernet Connection I217-LM")
        self.assertEqual(nic.firmware_version, "1.2.3.4")

    def test_adds_sriov_info(self):
        node = factory.make_Node()
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        nic = Interface.objects.get(mac_address="00:00:00:00:00:01")
        self.assertEqual(nic.sriov_max_vf, 8)

    def test_adds_sriov_tag_if_sriov(self):
        node = factory.make_Node()
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        nic1 = Interface.objects.get(mac_address="00:00:00:00:00:01")
        nic2 = Interface.objects.get(mac_address="00:00:00:00:00:02")
        nic3 = Interface.objects.get(mac_address="00:00:00:00:00:03")
        self.assertEqual(nic1.tags, ["sriov"])
        self.assertEqual(nic2.tags, [])
        self.assertEqual(nic3.tags, [])

    def test_skip_ifaces_under_sriov_if_deployed_pod(self):
        pod = factory.make_Pod()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        pod.hints.nodes.add(node)
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        data = make_lxd_output()
        data["resources"]["network"]["cards"].append(
            {
                "driver": "thunder-nic",
                "driver_version": "1.0",
                "sriov": {
                    "current_vfs": 30,
                    "maximum_vfs": 128,
                    "vfs": [
                        {
                            "driver": "thunder-nicvf",
                            "driver_version": "1.0",
                            "ports": [
                                {
                                    "id": "enP2p1s0f1",
                                    "address": "01:01:01:01:01:01",
                                    "port": 0,
                                    "protocol": "ethernet",
                                    "auto_negotiation": False,
                                    "link_detected": False,
                                }
                            ],
                            "numa_node": 0,
                            "vendor": "Cavium, Inc.",
                            "vendor_id": "177d",
                            "product": "THUNDERX Network Interface Controller virtual function",
                            "product_id": "a034",
                        }
                    ],
                },
                "numa_node": 0,
                "pci_address": "0002:01:00.0",
                "vendor": "Cavium, Inc.",
                "vendor_id": "177d",
                "product": "THUNDERX Network Interface Controller",
                "product_id": "a01e",
            }
        )
        update_node_network_information(node, data, create_numa_nodes(node))
        self.assertFalse(
            Interface.objects.filter(mac_address="01:01:01:01:01:01").exists()
        )

    def test_adds_ifaces_under_sriov_if_not_deployed(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        data = make_lxd_output()
        port = {
            "id": "enP2p1s0f1",
            "address": "01:01:01:01:01:01",
            "port": 0,
            "protocol": "ethernet",
            "auto_negotiation": False,
            "link_detected": False,
        }
        card = {
            "driver": "thunder-nic",
            "driver_version": "1.0",
            "sriov": {
                "current_vfs": 30,
                "maximum_vfs": 128,
                "vfs": [
                    {
                        "driver": "thunder-nicvf",
                        "driver_version": "1.0",
                        "ports": [port],
                        "numa_node": 0,
                        "vendor": "Cavium, Inc.",
                        "vendor_id": "177d",
                        "product": "THUNDERX Network Interface Controller virtual function",
                        "product_id": "a034",
                    }
                ],
            },
            "numa_node": 0,
            "pci_address": "0002:01:00.0",
            "vendor": "Cavium, Inc.",
            "vendor_id": "177d",
            "product": "THUNDERX Network Interface Controller",
            "product_id": "a01e",
        }
        data["resources"]["network"]["cards"].append(card)
        data["networks"][port["id"]] = {
            "hwaddr": port["address"],
            "type": "broadcast",
            "addresses": [],
            "vlan": None,
            "bridge": None,
            "bond": None,
            "state": "up",
        }
        update_node_network_information(node, data, create_numa_nodes(node))
        nic = Interface.objects.get(mac_address="01:01:01:01:01:01")
        self.assertEqual(nic.vendor, "Cavium, Inc.")

    def test_ignores_missing_vendor_data(self):
        """Test a node that has no previously known interfaces gets info from
        lshw added.
        """
        node = factory.make_Node()
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        data = make_lxd_output()
        card_info = data["resources"]["network"]["cards"][0]
        del card_info["vendor"]
        del card_info["product"]
        del card_info["firmware_version"]
        update_node_network_information(node, data, create_numa_nodes(node))

        nic = Interface.objects.get(mac_address="00:00:00:00:00:01")
        self.assertIsNone(nic.vendor)
        self.assertIsNone(nic.product)
        self.assertIsNone(nic.firmware_version)

    def test_one_mac_missing(self):
        """Test whether we correctly detach a NIC that no longer appears to be
        connected to the node.
        """
        node = factory.make_Node()
        # Create a MAC address that we know is not in the test dataset.
        factory.make_Interface(node=node, mac_address="01:23:45:67:89:ab")

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        # These should have been added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

        db_macaddresses = [
            iface.mac_address
            for iface in node.current_config.interface_set.all()
        ]
        self.assertNotIn("01:23:45:67:89:ab", db_macaddresses)

    def test_reassign_mac(self):
        """Test whether we can assign a MAC address previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()

        # Create a MAC address that we know IS in the test dataset.
        interface_to_be_reassigned = factory.make_Interface(node=node1)
        interface_to_be_reassigned.mac_address = "00:00:00:00:00:01"
        interface_to_be_reassigned.save()

        node2 = factory.make_Node()
        update_node_network_information(
            node2, make_lxd_output(), create_numa_nodes(node2)
        )

        self.assert_expected_interfaces_and_macs_exist_for_node(node2)

        # Ensure the MAC object moved over to node2.
        self.assertCountEqual(
            [], Interface.objects.filter(node_config=node1.current_config)
        )

    def test_reassign_interfaces(self):
        """Test whether we can assign interfaces previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()

        update_node_network_information(
            node1, make_lxd_output(), create_numa_nodes(node1)
        )

        # First make sure the first node has all the expected interfaces.
        self.assert_expected_interfaces_and_macs_exist_for_node(node1)

        # Grab the id from one of the created interfaces.
        interface_id = (
            PhysicalInterface.objects.filter(node_config=node1.current_config)
            .first()
            .id
        )

        # Now make sure the second node has them all.
        node2 = factory.make_Node()
        update_node_network_information(
            node2, make_lxd_output(), create_numa_nodes(node2)
        )

        self.assert_expected_interfaces_and_macs_exist_for_node(node2)

        # Now make sure all the objects moved to the second node.
        self.assertCountEqual(
            [], Interface.objects.filter(node_config=node1.current_config)
        )

        # ... and ensure that the interface was deleted.
        self.assertCountEqual([], Interface.objects.filter(id=interface_id))

    def test_deletes_virtual_interfaces_with_shared_mac(self):
        # Note: since this VLANInterface will be linked to the default VLAN
        # ("vid 0", which is actually invalid) the VLANInterface will
        # automatically get the name "vlan0".
        eth0_mac = self.EXPECTED_INTERFACES["eth0"]
        eth1_mac = self.EXPECTED_INTERFACES["eth1"]
        BOND_NAME = "bond0"
        node = factory.make_Node()

        eth0 = factory.make_Interface(
            name="eth0", mac_address=eth0_mac, node=node
        )
        eth1 = factory.make_Interface(
            name="eth1", mac_address=eth1_mac, node=node
        )

        factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            mac_address=eth0_mac,
            parents=[eth0],
            node=node,
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            mac_address=eth1_mac,
            parents=[eth1],
            node=node,
            name=BOND_NAME,
        )

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_interface_name_changed(self):
        eth0_mac = self.EXPECTED_INTERFACES["eth1"]
        node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            mac_address=eth0_mac,
            node=node,
        )
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        # This will ensure that the interface was renamed appropriately.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_mac_id_is_preserved(self):
        """Test whether MAC address entities are preserved and not recreated"""
        eth0_mac = self.EXPECTED_INTERFACES["eth0"]
        node = factory.make_Node()
        iface_to_be_preserved = factory.make_Interface(
            mac_address=eth0_mac, node=node
        )

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        self.assertIsNotNone(reload_object(iface_to_be_preserved))

    def test_legacy_model_upgrade_preserves_interfaces(self):
        eth0_mac = self.EXPECTED_INTERFACES["eth0"]
        eth1_mac = self.EXPECTED_INTERFACES["eth1"]
        node = factory.make_Node()
        eth0 = factory.make_Interface(mac_address=eth0_mac, node=node)
        eth1 = factory.make_Interface(mac_address=eth1_mac, node=node)
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        self.assertEqual(eth0, Interface.objects.get(id=eth0.id))
        self.assertEqual(eth1, Interface.objects.get(id=eth1.id))

        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_legacy_model_with_extra_mac(self):
        eth0_mac = self.EXPECTED_INTERFACES["eth0"]
        eth1_mac = self.EXPECTED_INTERFACES["eth1"]
        eth2_mac = self.EXPECTED_INTERFACES["eth2"]
        eth3_mac = "00:00:00:00:01:04"
        node = factory.make_Node()
        eth0 = factory.make_Interface(mac_address=eth0_mac, node=node)
        eth1 = factory.make_Interface(mac_address=eth1_mac, node=node)
        eth2 = factory.make_Interface(mac_address=eth2_mac, node=node)
        eth3 = factory.make_Interface(mac_address=eth3_mac, node=node)

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        self.assert_expected_interfaces_and_macs_exist_for_node(node)

        # Make sure we re-used the existing MACs in the database.
        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNotNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(eth2))

        # Make sure the interface that no longer exists has been removed.
        self.assertIsNone(reload_object(eth3))

    def test_deletes_virtual_interfaces_with_unique_mac(self):
        eth0_mac = self.EXPECTED_INTERFACES["eth0"]
        eth1_mac = self.EXPECTED_INTERFACES["eth1"]
        BOND_MAC = "00:00:00:00:01:02"
        node = factory.make_Node()
        eth0 = factory.make_Interface(mac_address=eth0_mac, node=node)
        eth1 = factory.make_Interface(mac_address=eth1_mac, node=node)
        factory.make_Interface(INTERFACE_TYPE.VLAN, node=node, parents=[eth0])
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            mac_address=BOND_MAC,
            node=node,
            parents=[eth1],
        )

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_deletes_virtual_interfaces_linked_to_removed_macs(self):
        VLAN_MAC = "00:00:00:00:01:01"
        BOND_MAC = "00:00:00:00:01:02"
        node = factory.make_Node()
        eth0 = factory.make_Interface(
            name="eth0", mac_address=VLAN_MAC, node=node
        )
        eth1 = factory.make_Interface(
            name="eth1", mac_address=BOND_MAC, node=node
        )
        factory.make_Interface(
            INTERFACE_TYPE.VLAN, mac_address=VLAN_MAC, parents=[eth0]
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=BOND_MAC, parents=[eth1]
        )

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_creates_discovered_ip_address(self):
        node = factory.make_Node()
        cidr = "192.168.0.3/24"
        subnet = factory.make_Subnet(
            cidr=cidr, vlan=VLAN.objects.get_default_vlan()
        )
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        eth0 = Interface.objects.get(
            node_config=node.current_config, name="eth0"
        )
        address = str(IPNetwork(cidr).ip)
        ipv4_ip = eth0.ip_addresses.get(ip=address)
        self.assertThat(
            ipv4_ip,
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet, ip=address
            ),
        )

    def test_handles_disconnected_interfaces(self):
        node = factory.make_Node()
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        eth1 = Interface.objects.get(
            node_config=node.current_config, name="eth1"
        )
        self.assertIsNone(eth1.vlan)

    def test_disconnects_previously_connected_interface(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        eth1 = factory.make_Interface(
            name="eth1",
            node=node,
            mac_address="00:00:00:00:00:02",
            subnet=subnet,
        )
        self.assertEqual(eth1.vlan, subnet.vlan)

        data = make_lxd_output()
        data["networks"]["eth1"]["addresses"] = []
        update_node_network_information(node, data, create_numa_nodes(node))
        eth1 = Interface.objects.get(
            node_config=node.current_config, name="eth1"
        )
        self.assertIsNone(eth1.vlan)

    def test_ignores_openbmc_interface(self):
        """Ensure that OpenBMC interface is ignored."""
        SWITCH_OPENBMC_MAC = "02:00:00:00:00:02"
        node = factory.make_Node()
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()

        data = make_lxd_output()
        open_bmc_port = data["resources"]["network"]["cards"][0]["ports"][0]
        open_bmc_port["address"] = SWITCH_OPENBMC_MAC
        data["networks"][open_bmc_port["id"]]["hwaddr"] = SWITCH_OPENBMC_MAC

        update_node_network_information(node, data, create_numa_nodes(node))

        # Specifically, there is no OpenBMC interface with a fixed MAC address.
        node_interfaces = Interface.objects.filter(
            node_config=node.current_config
        )
        all_macs = [interface.mac_address for interface in node_interfaces]
        self.assertNotIn(SWITCH_OPENBMC_MAC, all_macs)

    def test_sets_boot_interface(self):
        """Test a node will have its boot_interface set if none are defined."""
        subnet = factory.make_Subnet(cidr="192.168.0.3/24")
        node = factory.make_Node()

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_config=node.current_config).delete()
        node.boot_interface = None
        node.boot_cluster_ip = "192.168.0.1"
        node.save()
        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )
        node = reload_object(node)

        self.assertIsNotNone(
            node.boot_interface.vlan.subnet_set.filter(id=subnet.id).first()
        )

    def test_regenerates_testing_script_set(self):
        factory.make_Subnet(cidr="192.168.0.3/24")
        node = factory.make_Node(boot_cluster_ip="192.168.0.1")
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        node.current_testing_script_set = (
            ScriptSet.objects.create_testing_script_set(
                node=node, scripts=[script.name]
            )
        )
        node.save()

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        self.assertEqual(1, len(node.get_latest_testing_script_results))
        # The default network layout only configures the boot interface.
        script_result = node.get_latest_testing_script_results.get(
            script=script
        )
        self.assertDictEqual(
            {
                "interface": {
                    "type": "interface",
                    "value": {
                        "id": node.boot_interface.id,
                        "name": node.boot_interface.name,
                        "mac_address": str(node.boot_interface.mac_address),
                        "vendor": node.boot_interface.vendor,
                        "product": node.boot_interface.product,
                    },
                }
            },
            script_result.parameters,
        )

    def test_sets_default_configuration(self):
        factory.make_Subnet(cidr="192.168.0.3/24")
        node = factory.make_Node(boot_cluster_ip="192.168.0.1")

        update_node_network_information(
            node, make_lxd_output(), create_numa_nodes(node)
        )

        # 2 devices configured, one for IPv4 one for IPv6.
        self.assertEqual(
            2,
            node.current_config.interface_set.filter(
                ip_addresses__alloc_type=IPADDRESS_TYPE.AUTO
            ).count(),
        )

    def test_create_bond_with_no_link_parents(self):
        boot_subnet = factory.make_Subnet(cidr="192.168.0.3/24")
        interface = factory.make_Interface(subnet=boot_subnet)
        node = interface.node_config.node
        node.boot_cluster_ip = "192.168.0.1"
        node.boot_interface = interface
        node.save()
        output = make_lxd_output()
        mac1 = factory.make_mac_address()
        mac2 = factory.make_mac_address()
        output["networks"] = {
            "bond0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "hwaddr": mac1,
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
                "bond": {
                    "mode": "802.3ad",
                    "transmit_policy": "layer3+4",
                    "up_delay": 0,
                    "down_delay": 0,
                    "mii_frequency": 100,
                    "mii_state": "down",
                    "lower_devices": ["ens6f0", "ens5f0"],
                },
                "bridge": None,
                "vlan": None,
            },
            "bond0.108": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "hwaddr": mac1,
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": {"lower_device": "bond0", "vid": 108},
            },
            "br0": {
                "addresses": [
                    {
                        "family": "inet",
                        "address": factory.make_ipv4_address(),
                        "netmask": "24",
                        "scope": "global",
                    },
                    {
                        "family": "inet6",
                        "address": factory.make_ipv6_address(),
                        "netmask": "64",
                        "scope": "link",
                    },
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 634,
                    "packets_received": 0,
                    "packets_sent": 7,
                },
                "hwaddr": mac1,
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
                "bond": None,
                "bridge": {
                    "id": "8000.46145500a9dc",
                    "stp": False,
                    "forward_delay": 1500,
                    "vlan_default": 1,
                    "vlan_filtering": False,
                    "upper_devices": ["bond0.108"],
                },
                "vlan": None,
            },
            "ens5f0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "hwaddr": mac1,
                "mtu": 1500,
                "state": "down",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
            "ens6f0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "hwaddr": mac2,
                "mtu": 1500,
                "state": "down",
                "type": "broadcast",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
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
                "counters": {
                    "bytes_received": 9125228383,
                    "bytes_sent": 9125228383,
                    "packets_received": 2211361,
                    "packets_sent": 2211361,
                },
                "hwaddr": "",
                "mtu": 65536,
                "state": "up",
                "type": "loopback",
                "bond": None,
                "bridge": None,
                "vlan": None,
            },
        }
        process_lxd_results(node, json.dumps(output).encode(), 0)
        node.refresh_from_db()
        ens5 = node.current_config.interface_set.get(name="ens5f0")
        ens6 = node.current_config.interface_set.get(name="ens6f0")
        bond = node.current_config.interface_set.get(name="bond0")
        vlan = node.current_config.interface_set.get(name="bond0.108")
        bridge = node.current_config.interface_set.get(name="br0")
        self.assertCountEqual(list(bond.parents.all()), [ens5, ens6])
        self.assertFalse(ens5.link_connected)
        self.assertFalse(ens6.link_connected)
        self.assertTrue(bond.link_connected)
        self.assertTrue(vlan.link_connected)
        self.assertTrue(bridge.link_connected)


class TestUpdateBootInterface(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.hook = NODE_INFO_SCRIPTS[KERNEL_CMDLINE_OUTPUT_NAME]["hook"]
        self.node = factory.make_Node(with_boot_disk=False)

    def test_sets_boot_interface_bootif(self):
        Interface.objects.filter(node_config=self.node.current_config).delete()
        nic1 = factory.make_Interface(node=self.node)
        nic2 = factory.make_Interface(node=self.node)
        kernel_cmdline1 = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(nic1.mac_address).replace(":", "-")
        )
        kernel_cmdline2 = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(nic2.mac_address).replace(":", "-")
        )

        self.hook(self.node, kernel_cmdline1.encode("utf-8"), 0)
        self.node = reload_object(self.node)
        self.assertEqual(nic1, self.node.boot_interface)

        self.hook(self.node, kernel_cmdline2.encode("utf-8"), 0)
        self.node = reload_object(self.node)
        self.assertEqual(nic2, self.node.boot_interface)

    def test_boot_interface_bootif_no_such_mac(self):
        Interface.objects.filter(node_config=self.node.current_config).delete()
        kernel_cmdline = KERNEL_CMDLINE_OUTPUT.format(
            mac_address="11-22-33-44-55-66"
        )
        logger = self.useFixture(FakeLogger())

        self.hook(self.node, kernel_cmdline.encode("utf-8"), 0)
        self.node = reload_object(self.node)

        self.assertIn(
            "BOOTIF interface 11:22:33:44:55:66 doesn't exist", logger.output
        )

    def test_boot_interface_bootif_bonded_interfaces(self):
        mac_address = factory.make_mac_address()
        parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=self.node, mac_address=mac_address
        )
        parent2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=self.node,
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            parents=[parent, parent2],
            node=self.node,
            mac_address=mac_address,
        )
        kernel_cmdline = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(mac_address).replace(":", "-")
        )
        logger = self.useFixture(FakeLogger())

        self.hook(self.node, kernel_cmdline.encode("utf-8"), 0)
        self.node = reload_object(self.node)

        self.assertEqual(parent, self.node.boot_interface)
        self.assertEqual("", logger.output)

    def test_no_bootif(self):
        Interface.objects.filter(node_config=self.node.current_config).delete()
        nic = factory.make_Interface(node=self.node)
        self.node.boot_interface = nic
        self.node.save()

        self.hook(self.node, b"no bootif mac", 0)
        self.node = reload_object(self.node)

        self.assertEqual(nic, self.node.boot_interface)

    def test_non_zero_exit_status(self):
        Interface.objects.filter(node_config=self.node.current_config).delete()
        nic = factory.make_Interface(node=self.node)
        self.node.boot_interface = None
        self.node.save()
        kernel_cmdline = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(nic.mac_address).replace(":", "-")
        )

        logger = self.useFixture(FakeLogger())
        self.hook(self.node, kernel_cmdline.encode("utf-8"), 1)
        self.node = reload_object(self.node)
        self.assertIsNone(self.node.boot_interface)

        self.assertIn("kernel-cmdline failed with status: 1", logger.output)


class TestHardwareSyncNotify(MAASServerTestCase):
    def setup(self):
        details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE]
        EventType.objects.register(
            details.name, details.description, details.level
        )

    def test_hardware_sync_notify_does_not_create_event_without_hw_sync(self):
        node = factory.make_Node()
        block_device = factory.make_BlockDevice(node=node)
        _hardware_sync_notify(
            EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE,
            node,
            block_device,
            HARDWARE_SYNC_ACTIONS.ADDED,
        )
        self.assertEqual(0, Event.objects.count())

    def test_hardware_sync_notify_does_not_create_event_if_not_deployed(self):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.COMMISSIONING
        )
        block_device = factory.make_BlockDevice(node=node)
        _hardware_sync_notify(
            EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE,
            node,
            block_device,
            HARDWARE_SYNC_ACTIONS.ADDED,
        )
        self.assertEqual(0, Event.objects.count())

    def test_hardware_sync_notify_creates_event(self):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        block_device = factory.make_BlockDevice(node=node)
        _hardware_sync_notify(
            EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE,
            node,
            block_device,
            HARDWARE_SYNC_ACTIONS.ADDED,
        )
        self.assertEqual(1, Event.objects.count())


class TestHardwareSyncBlockDeviceNotify(MAASServerTestCase):
    def setup(self):
        details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE]
        EventType.objects.register(
            details.name, details.description, details.level
        )

    def test_hardware_sync_block_device_notify_creates_event(self):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        block_device = factory.make_BlockDevice(node=node)
        _hardware_sync_block_device_notify(
            node, block_device, HARDWARE_SYNC_ACTIONS.ADDED
        )
        event = Event.objects.get(
            type__name=EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE
        )
        self.assertEqual(event.action, HARDWARE_SYNC_ACTIONS.ADDED)
        self.assertEqual(
            event.description,
            f"block device {block_device.name} was added on node {node.system_id}",
        )


class TestHardwareSyncNodeDeviceNotify(MAASServerTestCase):
    def setup(self):
        pci_details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_PCI_DEVICE]
        usb_details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_USB_DEVICE]
        EventType.objects.register(
            pci_details.name, pci_details.description, pci_details.level
        )
        EventType.objects.register(
            usb_details.name, usb_details.description, usb_details.level
        )

    def test_hardware_sync_node_device_notify_creates_pci_event_for_pci_device(
        self,
    ):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        pci_device = factory.make_NodeDevice(bus=NODE_DEVICE_BUS.PCIE)
        _hardware_sync_node_device_notify(
            node, pci_device, HARDWARE_SYNC_ACTIONS.ADDED
        )
        event = Event.objects.get(
            type__name=EVENT_TYPES.NODE_HARDWARE_SYNC_PCI_DEVICE
        )
        self.assertEqual(event.action, HARDWARE_SYNC_ACTIONS.ADDED)
        self.assertEqual(
            event.description,
            f"pci device {pci_device.device_number} was added on node {node.system_id}",
        )


class TestHardwareSyncCPUNotify(MAASServerTestCase):
    def setup(self):
        details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_CPU]
        EventType.objects.register(
            details.name, details.description, details.level
        )

    def test_hardware_sync_cpu_notify_creates_cpu_event(self):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        cpu_model = factory.make_name("cpu-model")
        _hardware_sync_cpu_notify(node, cpu_model, HARDWARE_SYNC_ACTIONS.ADDED)
        event = Event.objects.get(
            type__name=EVENT_TYPES.NODE_HARDWARE_SYNC_CPU
        )
        self.assertEqual(event.action, HARDWARE_SYNC_ACTIONS.ADDED)
        self.assertEqual(
            event.description,
            f"cpu {cpu_model} was added on node {node.system_id}",
        )


class TestHardwareSyncMemoryNotify(MAASServerTestCase):
    def setup(self):
        details = EVENT_DETAILS[EVENT_TYPES.NODE_HARDWARE_SYNC_MEMORY]
        EventType.objects.register(
            details.name, details.description, details.level
        )

    def test_hardware_sync_memory_notify_creates_memory(self):
        node = factory.make_Node(
            enable_hw_sync=True, status=NODE_STATUS.DEPLOYED
        )
        old_memory = node.memory
        node.memory = 1073741824
        _hardware_sync_memory_notify(node, old_memory)
        event = Event.objects.get(
            type__name=EVENT_TYPES.NODE_HARDWARE_SYNC_MEMORY
        )
        self.assertEqual(event.action, HARDWARE_SYNC_ACTIONS.ADDED)
        self.assertEqual(
            event.description,
            f"1.1 GB of memory was added on node {node.system_id}",
        )


class TestParseInterfaces(MAASServerTestCase):
    def test_skips_ipoib_mac(self):
        node = factory.make_Node(with_boot_disk=False, interface=True)
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        resources.update(SAMPLE_LXD_RESOURCES_NETWORK_LP1939456)
        data = make_lxd_output(
            resources=resources, networks=SAMPLE_LXD_NETWORK_LP1939456
        )
        interfaces = parse_interfaces(node, data)
        self.assertEqual(
            interfaces.keys(),
            {"44:a8:42:ba:a3:b4", "44:a8:42:ba:a3:b6", "10:98:36:99:7d:9e"},
        )
