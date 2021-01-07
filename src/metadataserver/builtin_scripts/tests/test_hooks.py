# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test hooks."""


from copy import deepcopy
import json
import os.path
import random

from distro_info import UbuntuDistroInfo
from django.db.models import Q
from fixtures import FakeLogger
from netaddr import IPNetwork
from testtools.matchers import (
    Contains,
    ContainsAll,
    Equals,
    Is,
    MatchesStructure,
    Not,
)

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_METADATA,
    NODE_STATUS,
)
from maasserver.fields import MAC
from maasserver.models import node as node_module
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.config import Config
from maasserver.models.interface import Interface
from maasserver.models.nodemetadata import NodeMetadata
from maasserver.models.numa import NUMANode
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.switch import Switch
from maasserver.models.tag import Tag
from maasserver.models.vlan import VLAN
from maasserver.storage_layouts import get_applied_storage_layout_for_node
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import MockNotCalled
from maastesting.testcase import MAASTestCase
import metadataserver.builtin_scripts.hooks as hooks_module
from metadataserver.builtin_scripts.hooks import (
    add_switch,
    add_switch_vendor_model_tags,
    create_metadata_by_modalias,
    detect_switch_vendor_model,
    determine_hardware_matches,
    filter_modaliases,
    get_dmi_data,
    NODE_INFO_SCRIPTS,
    parse_bootif_cmdline,
    process_lxd_results,
    retag_node_for_hardware_by_modalias,
    SWITCH_OPENBMC_MAC,
    update_node_fruid_metadata,
    update_node_network_information,
    update_node_physical_block_devices,
)
from metadataserver.enum import SCRIPT_STATUS, SCRIPT_TYPE
from metadataserver.models import ScriptSet
from provisioningserver.refresh.node_info_scripts import (
    IPADDR_OUTPUT_NAME,
    KERNEL_CMDLINE_OUTPUT_NAME,
    LXD_OUTPUT_NAME,
)
from provisioningserver.utils.tests.test_lxd import SAMPLE_LXD_RESOURCES

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


# This matches ip_addr_results_xenial.txt for the unit tests
SAMPLE_LXD_XENIAL_NETWORK = {
    "cards": [
        {
            "driver": "e1000e",
            "driver_version": "3.2.6-k",
            "ports": [
                {
                    "id": "ens3",
                    "address": "52:54:00:2d:39:49",
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
        },
        {
            "driver": "e1000e",
            "driver_version": "3.2.6-k",
            "ports": [
                {
                    "id": "ens10",
                    "address": "52:54:00:e5:c6:6b",
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
            "numa_node": 0,
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
                    "id": "ens11",
                    "address": "52:54:00:ed:9f:9d",
                    "port": 0,
                    "protocol": "ethernet",
                    "auto_negotiation": False,
                    "link_detected": False,
                }
            ],
            "numa_node": 1,
            "pci_address": "0000:04:00.0",
            "vendor": "Intel Corporation",
            "vendor_id": "8086",
            "product": "Wireless 7260",
            "product_id": "08b2",
        },
        {
            "driver": "e1000e",
            "driver_version": "3.2.6-k",
            "ports": [
                {
                    "id": "ens12",
                    "address": "52:54:00:ed:9f:00",
                    "port": 0,
                    "protocol": "ethernet",
                    "auto_negotiation": False,
                    "link_detected": False,
                }
            ],
            "numa_node": 1,
            "pci_address": "0000:04:00.0",
            "vendor": "Intel Corporation",
            "vendor_id": "8086",
            "product": "Wireless 7260",
            "product_id": "08b2",
        },
    ],
    "total": 4,
}


IP_ADDR_OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__), "ip_addr_results.txt"
)
with open(IP_ADDR_OUTPUT_FILE, "rb") as fd:
    IP_ADDR_OUTPUT = fd.read()
    IP_ADDR_OUTPUT_FILE = os.path.join(
        os.path.dirname(__file__), "ip_addr_results_xenial.txt"
    )
with open(IP_ADDR_OUTPUT_FILE, "rb") as fd:
    IP_ADDR_OUTPUT_XENIAL = fd.read()
    IP_ADDR_WEDGE_OUTPUT_FILE = os.path.join(
        os.path.dirname(__file__), "ip_addr_results_wedge100.txt"
    )
with open(IP_ADDR_WEDGE_OUTPUT_FILE, "rb") as fd:
    IP_ADDR_WEDGE_OUTPUT = fd.read()

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


def make_lxd_output(
    resources=None,
    api_extensions=None,
    api_version=None,
    kernel_architecture=None,
    kernel_version=None,
    os_name=None,
    os_version=None,
    server_name=None,
    virt_type=None,
    with_xenial_network=False,
    uuid=None,
):
    if not resources:
        resources = deepcopy(SAMPLE_LXD_RESOURCES)
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
    }
    ret["resources"]["system"] = make_lxd_system_info(virt_type, uuid)
    if with_xenial_network:
        ret["resources"]["network"] = deepcopy(SAMPLE_LXD_XENIAL_NETWORK)
    return ret


def make_lxd_output_json(*args, **kwargs):
    return json.dumps(make_lxd_output(*args, **kwargs)).encode()


def create_IPADDR_OUTPUT_NAME_script(node, output):
    commissioning_script_set = (
        ScriptSet.objects.create_commissioning_script_set(node)
    )
    script_result = commissioning_script_set.find_script_result(
        script_name=IPADDR_OUTPUT_NAME
    )
    if script_result is not None:
        script_result.delete()
    node.current_commissioning_script_set = commissioning_script_set
    factory.make_ScriptResult(
        script_set=commissioning_script_set,
        script_name=IPADDR_OUTPUT_NAME,
        exit_status=0,
        status=SCRIPT_STATUS.PASSED,
        output=output,
    )


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
        self.assertThat(detected, Equals(self.result))

    def test_get_dmi_data(self):
        dmi_data = get_dmi_data(self.modaliases)
        self.assertThat(dmi_data, Equals(self.dmi_data))


class TestDetectSwitchVendorModel(MAASServerTestCase):
    def test_detect_switch_vendor_model_returns_none_by_default(self):
        detected = detect_switch_vendor_model(set())
        self.assertThat(detected, Equals((None, None)))


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
        self.assertThat(matches, Equals(self.result))


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
        self.assertThat(discovered, Equals(expected_matches))
        self.assertThat(ruled_out, Equals(expected_ruled_out))

    def test_retag_node_for_hardware_by_modalias__precreate_parent(self):
        node = factory.make_Node()
        parent_tag = factory.make_Tag()
        parent_tag_name = parent_tag.name
        # Need to pre-create these so the code can remove them.
        expected_removed = set(
            [
                factory.make_Tag(name=self.hardware_database[index]["tag"])
                for index in self.expected_ruled_out_indexes
            ]
        )
        for tag in expected_removed:
            node.tags.add(tag)
        added, removed = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database
        )
        expected_added = set(
            [
                Tag.objects.get(name=self.hardware_database[index]["tag"])
                for index in self.expected_match_indexes
            ]
        )
        if len(expected_added) > 0:
            expected_added.add(parent_tag)
        else:
            expected_removed.add(parent_tag)
        self.assertThat(added, Equals(expected_added))
        self.assertThat(removed, Equals(expected_removed))
        # Run again to confirm that we added the same tags.
        added, removed = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database
        )
        self.assertThat(added, Equals(expected_added))

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
        self.assertThat(tags, Equals({"accton", "wedge40"}))
        tag = Tag.objects.get(name="wedge40")
        self.assertThat(
            tag.kernel_opts, Equals("console=tty0 console=ttyS1,57600n8")
        )

    def test_sets_wedge100_kernel_opts(self):
        node = factory.make_Node()
        add_switch_vendor_model_tags(node, "accton", "wedge100")
        tags = set(node.tags.all().values_list("name", flat=True))
        self.assertThat(tags, Equals({"accton", "wedge100"}))
        tag = Tag.objects.get(name="wedge100")
        self.assertThat(
            tag.kernel_opts, Equals("console=tty0 console=ttyS4,57600n8")
        )


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
                "expected_driver": "",
                "expected_vendor": "accton",
                "expected_model": "wedge40",
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
                "expected_driver": "",
                "expected_vendor": "accton",
                "expected_model": "wedge100",
            },
        ),
        (
            "no_matcj",
            {
                "modaliases": b"pci:xxx\n" b"pci:yyy\n",
                "expected_tags": set(),
                "expected_driver": None,
                "expected_vendor": None,
                "expected_model": None,
            },
        ),
    )

    def test_tags_node_appropriately(self):
        node = factory.make_Node()
        create_metadata_by_modalias(node, self.modaliases, 0)
        tags = set(node.tags.all().values_list("name", flat=True))
        self.assertThat(tags, Equals(self.expected_tags))
        if self.expected_driver is not None:
            switch = Switch.objects.get(node=node)
            self.assertThat(switch.nos_driver, Equals(self.expected_driver))
        metadata = node.get_metadata()
        self.assertThat(
            metadata.get("vendor-name"), Equals(self.expected_vendor)
        )
        self.assertThat(
            metadata.get("physical-model-name"), Equals(self.expected_model)
        )


class TestAddSwitchModels(MAASServerTestCase):
    def test_sets_switch_driver_to_empty_string(self):
        node = factory.make_Node()
        switch = add_switch(node, "vendor", "switch")
        self.assertEqual("", switch.nos_driver)
        metadata = node.get_metadata()
        self.assertEqual("vendor", metadata["vendor-name"])
        self.assertEqual("switch", metadata["physical-model-name"])


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
                for l, w in v.items():
                    if not w or w in ["0123456789", "none"]:
                        del data[k][v][l]
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
        required_extensions = set(
            ["resources", "resources_v2", "api_os", "resources_system"]
        )
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
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
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
        self.assertEquals(deb_arch, node.architecture)

    def test_sets_uuid(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        uuid = factory.make_UUID()
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        node = reload_object(node)
        self.assertEquals(uuid, node.hardware_uuid)

    def test_sets_empty_uuid(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
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
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        self.assertIsNone(reload_object(node).hardware_uuid)
        self.assertIsNone(reload_object(duplicate_uuid_node).hardware_uuid)

    def test_ignores_invalid_uuid(self):
        uuid = factory.make_name("invalid_uuid")
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        process_lxd_results(node, make_lxd_output_json(uuid=uuid), 0)
        self.assertIsNone(reload_object(node).hardware_uuid)

    def test_sets_os_hostname_for_controller(self):
        rack = factory.make_RackController()
        create_IPADDR_OUTPUT_NAME_script(rack, IP_ADDR_OUTPUT)
        ubuntu_info = UbuntuDistroInfo()
        ubuntu_release = random.choice(
            [row.__dict__ for row in ubuntu_info._releases]
        )
        os_version = ubuntu_release["version"].replace(" LTS", "")
        server_name = factory.make_hostname()
        process_lxd_results(
            rack,
            make_lxd_output_json(
                os_version=os_version, server_name=server_name
            ),
            0,
        )
        rack = reload_object(rack)
        self.assertEquals("ubuntu", rack.osystem)
        self.assertEquals(ubuntu_release["series"], rack.distro_series)
        self.assertEquals(server_name, rack.hostname)

    def test_doesnt_set_os_for_controller_if_blank(self):
        osystem = factory.make_name("osystem")
        distro_series = factory.make_name("distro_series")
        rack = factory.make_RackController(
            osystem=osystem, distro_series=distro_series
        )
        create_IPADDR_OUTPUT_NAME_script(rack, IP_ADDR_OUTPUT)
        process_lxd_results(
            rack, make_lxd_output_json(os_name="", os_version=""), 0
        )
        rack = reload_object(rack)
        self.assertEquals(osystem, rack.osystem)
        self.assertEquals(distro_series, rack.distro_series)

    def test_sets_os_for_pod(self):
        pod = factory.make_Pod()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        pod.hints.nodes.add(node)
        ubuntu_info = UbuntuDistroInfo()
        ubuntu_release = random.choice(
            [row.__dict__ for row in ubuntu_info._releases]
        )
        os_version = ubuntu_release["version"].replace(" LTS", "")
        server_name = factory.make_hostname()
        process_lxd_results(
            node,
            make_lxd_output_json(
                os_version=os_version, server_name=server_name
            ),
            0,
        )
        node = reload_object(node)
        self.assertEquals("ubuntu", node.osystem)
        self.assertEquals(ubuntu_release["series"], node.distro_series)

    def test_ignores_os_for_machine(self):
        node = factory.make_Node(osystem="centos", distro_series="8")
        hostname = node.hostname
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        process_lxd_results(node, make_lxd_output_json(), 0)
        node = reload_object(node)
        self.assertEquals("centos", node.osystem)
        self.assertEquals("8", node.distro_series)
        self.assertEquals(hostname, node.hostname)

    def test_does_not_update_node_network_information_if_rack(self):
        rack = factory.make_RackController()
        mock_update_node_network_information = self.patch(
            hooks_module, "update_node_network_information"
        )
        process_lxd_results(rack, make_lxd_output_json(), 0)
        self.assertThat(mock_update_node_network_information, MockNotCalled())

    def test_does_not_update_node_network_information_if_region(self):
        region = factory.make_RegionController()
        mock_update_node_network_information = self.patch(
            hooks_module, "update_node_network_information"
        )
        process_lxd_results(region, make_lxd_output_json(), 0)
        self.assertThat(mock_update_node_network_information, MockNotCalled())

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
        self.assertItemsEqual(
            ["Intel Corporation", "Intel Corporation", "Intel Corporation"],
            [iface.vendor for iface in node.interface_set.all()],
        )

    def test_updates_memory(self):
        node = factory.make_Node()
        node.memory = random.randint(4096, 8192)
        node.save()
        self.patch(hooks_module, "update_node_network_information")

        process_lxd_results(node, make_lxd_output_json(), 0)
        node = reload_object(node)
        self.assertEqual(round(16691519488 / 1024 / 1024), node.memory)

    def test_updates_model_and_cpu_speed_from_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(hooks_module, "update_node_network_information")

        process_lxd_results(node, make_lxd_output_json(), 0)
        node = reload_object(node)
        self.assertEqual(2400, node.cpu_speed)
        nmd = NodeMetadata.objects.get(node=node, key="cpu_model")
        self.assertEqual("Intel(R) Core(TM) i7-4700MQ CPU", nmd.value)

    def test_updates_cpu_speed_with_max_frequency_when_not_in_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(hooks_module, "update_node_network_information")

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
        self.patch(hooks_module, "update_node_network_information")

        NO_NAME_OR_MAX_FREQ = deepcopy(SAMPLE_LXD_RESOURCES)
        del NO_NAME_OR_MAX_FREQ["cpu"]["sockets"][0]["name"]
        del NO_NAME_OR_MAX_FREQ["cpu"]["sockets"][0]["frequency_turbo"]
        process_lxd_results(node, make_lxd_output_json(NO_NAME_OR_MAX_FREQ), 0)
        node = reload_object(node)
        self.assertEqual(3200, node.cpu_speed)

    def test_updates_memory_numa_nodes(self):
        expected_memory = int(16691519488 / 2 / 1024 / 1024)
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.patch(hooks_module, "update_node_network_information")

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
        self.patch(hooks_module, "update_node_network_information")
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
        self.patch(hooks_module, "update_node_network_information")
        process_lxd_results(
            node, make_lxd_output_json(SAMPLE_LXD_RESOURCES), 0
        )
        for numa_node in NUMANode.objects.filter(node=node):
            self.assertFalse(numa_node.hugepages_set.exists())

    def test_updates_memory_numa_nodes_missing(self):
        total_memory = SAMPLE_LXD_RESOURCES_NO_NUMA["memory"]["total"]
        node = factory.make_Node()
        self.patch(hooks_module, "update_node_network_information")

        process_lxd_results(
            node, make_lxd_output_json(SAMPLE_LXD_RESOURCES_NO_NUMA), 0
        )
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(1, len(numa_nodes))
        for numa_node in numa_nodes:
            self.assertEqual(int(total_memory / 1024 / 1024), numa_node.memory)

    def test_accepts_numa_node_zero_memory(self):
        # Regression test for LP:1878923
        node = factory.make_Node()
        self.patch(hooks_module, "update_node_network_information")
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

        self.assertEquals(32158, node.memory)
        self.assertItemsEqual(
            [32158, 0], [numa.memory for numa in node.numanode_set.all()]
        )

    def test_updates_memory_no_corresponding_cpu_numa_node(self):
        # Regression test for LP:1885157
        node = factory.make_Node()
        self.patch(hooks_module, "update_node_network_information")
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
        self.patch(hooks_module, "update_node_network_information")

        process_lxd_results(node, make_lxd_output_json(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual([0, 1, 2, 3], numa_nodes[0].cores)
        self.assertEqual([4, 5, 6, 7], numa_nodes[1].cores)

    def test_updates_cpu_numa_nodes_per_thread(self):
        node = factory.make_Node()
        self.patch(hooks_module, "update_node_network_information")

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
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        process_lxd_results(node, make_lxd_output_json(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        node_interfaces = list(
            Interface.objects.filter(node=node).order_by("name")
        )
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual(node_interfaces[0].numa_node, numa_nodes[0])
        self.assertEqual(node_interfaces[1].numa_node, numa_nodes[1])
        self.assertEqual(node_interfaces[2].numa_node, numa_nodes[0])

    def test_updates_storage_numa_nodes(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        process_lxd_results(node, make_lxd_output_json(), 0)
        numa_nodes = NUMANode.objects.filter(node=node).order_by("index")
        node_interfaces = list(
            PhysicalBlockDevice.objects.filter(node=node).order_by("name")
        )
        self.assertEqual(2, len(numa_nodes))
        self.assertEqual(node_interfaces[0].numa_node, numa_nodes[0])
        self.assertEqual(node_interfaces[1].numa_node, numa_nodes[1])

    def test_allows_devices_on_sparse_numa_nodes(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        lxd_output = make_lxd_output()
        lxd_output["resources"]["cpu"]["sockets"][-1]["cores"][-1]["threads"][
            -1
        ]["numa_node"] = 16
        lxd_output["resources"]["network"]["cards"][-1]["numa_node"] = 16

        process_lxd_results(node, json.dumps(lxd_output).encode(), 0)

        self.assertEqual(
            16,
            node.interface_set.get(
                mac_address=lxd_output["resources"]["network"]["cards"][-1][
                    "ports"
                ][-1]["address"]
            ).numa_node.index,
        )

    def test_updates_interfaces_speed(self):
        node = factory.make_Node()
        iface = factory.make_Interface(
            node=node,
            mac_address="00:00:00:00:00:01",
            interface_speed=0,
            link_speed=0,
        )
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        process_lxd_results(node, make_lxd_output_json(), 0)
        # the existing interface gets updated
        iface1 = reload_object(iface)
        self.assertEqual(1000, iface1.link_speed)
        self.assertEqual(1000, iface1.interface_speed)
        # other interfaces get created
        iface2, iface3 = (
            Interface.objects.filter(node=node)
            .exclude(mac_address=iface.mac_address)
            .order_by("mac_address")
        )
        self.assertEqual(0, iface2.link_speed)
        self.assertEqual(1000, iface2.interface_speed)
        self.assertEqual(0, iface3.link_speed)
        self.assertEqual(0, iface3.interface_speed)

    def test_ipaddr_script_before(self):
        self.assertLess(
            IPADDR_OUTPUT_NAME,
            LXD_OUTPUT_NAME,
            "The LXD script hook depends on the IPADDR script result",
        )

    def test_processes_system_information(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        output = make_lxd_output()
        process_lxd_results(node, json.dumps(output).encode(), 0)
        self.assertSystemInformation(node, output)

    def test_ignores_system_information_placeholders(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        modified_sample_lxd_data = make_lxd_output()
        for k, v in modified_sample_lxd_data["resources"]["system"].items():
            if isinstance(v, dict):
                for l, w in v.items():
                    modified_sample_lxd_data["resources"]["system"][k][
                        l
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
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        modified_sample_lxd_data = make_lxd_output()
        for key in ["motherboard", "firmware", "chassis"]:
            modified_sample_lxd_data["resources"]["system"][key] = None
        process_lxd_results(
            node, json.dumps(modified_sample_lxd_data).encode(), 0
        )
        self.assertEquals(
            0,
            node.nodemetadata_set.filter(
                Q(key__startswith="mainboard")
                | Q(key__startswith="firmware")
                | Q(key__startswith="chassis")
            ).count(),
        )

    def test_removes_missing_nodemetadata(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
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
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        process_lxd_results(
            node, make_lxd_output_json(virt_type="physical"), 0
        )
        self.assertFalse(node.tags.filter(name="virtual").exists())

    def test_syncs_pods(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        pod.hints.nodes.add(node)
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        process_lxd_results(node, make_lxd_output_json(), 0)
        pod.hints.refresh_from_db()

        self.assertEquals(8, pod.hints.cores)
        self.assertEquals(2400, pod.hints.cpu_speed)
        self.assertEquals(15918, pod.hints.memory)
        self.assertEquals(2, pod.hints.local_disks)
        self.assertEquals(0, pod.hints.iscsi_storage)


class TestUpdateNodePhysicalBlockDevices(MAASServerTestCase):
    def test_idempotent_block_devices(self):
        device_names = [
            device["id"] for device in SAMPLE_LXD_RESOURCES["storage"]["disks"]
        ]
        node = factory.make_Node()
        numa_nodes = create_numa_nodes(node)
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, numa_nodes
        )
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, numa_nodes
        )
        devices = list(PhysicalBlockDevice.objects.filter(node=node))
        created_names = []
        for index, device in enumerate(devices):
            created_names.append(device.name)
            self.assertEqual(device.numa_node, numa_nodes[index])
        self.assertItemsEqual(device_names, created_names)

    def test_does_nothing_if_skip_storage(self):
        node = factory.make_Node(skip_storage=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, {}, create_numa_nodes(node))
        self.assertIsNotNone(reload_object(block_device))
        self.assertFalse(reload_object(node).skip_storage)

    def test_removes_previous_physical_block_devices(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, {}, create_numa_nodes(node))
        self.assertIsNone(reload_object(block_device))

    def test_creates_physical_block_devices(self):
        device_names = [
            device["id"] for device in SAMPLE_LXD_RESOURCES["storage"]["disks"]
        ]
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_names = [
            device.name
            for device in PhysicalBlockDevice.objects.filter(node=node)
        ]
        self.assertItemsEqual(device_names, created_names)

    def test_skips_read_only_and_cdroms(self):
        node = factory.make_Node()
        READ_ONLY_AND_CDROM = deepcopy(SAMPLE_LXD_RESOURCES)
        READ_ONLY_AND_CDROM["storage"]["disks"][0]["read_only"] = "true"
        READ_ONLY_AND_CDROM["storage"]["disks"][1]["type"] = "cdrom"
        update_node_physical_block_devices(
            node, READ_ONLY_AND_CDROM, create_numa_nodes(node)
        )
        created_names = [
            device.name
            for device in PhysicalBlockDevice.objects.filter(node=node)
        ]
        self.assertItemsEqual([], created_names)

    def test_handles_renamed_block_device(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        NEW_NAMES = deepcopy(SAMPLE_LXD_RESOURCES)
        NEW_NAMES["storage"]["disks"][0]["id"] = "sdy"
        NEW_NAMES["storage"]["disks"][1]["id"] = "sdz"
        update_node_physical_block_devices(
            node, NEW_NAMES, create_numa_nodes(node)
        )
        device_names = ["sdy", "sdz"]
        created_names = [
            device.name
            for device in PhysicalBlockDevice.objects.filter(node=node)
        ]
        self.assertItemsEqual(device_names, created_names)

    def test_handles_new_block_device_in_front(self):
        # First simulate a node being commissioned with two disks. For
        # this test, there need to be at least two disks in order to
        # simulate a condition like the one in bug #1662343.
        node = factory.make_Node()
        update_node_physical_block_devices(
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
        update_node_physical_block_devices(
            node, NEW_NAMES, create_numa_nodes(node)
        )
        device_names = [
            (device.name, device.serial)
            for device in PhysicalBlockDevice.objects.filter(node=node)
        ]
        self.assertItemsEqual(
            [
                ("sdx", NEW_NAMES["storage"]["disks"][0]["serial"]),
                ("sdy", NEW_NAMES["storage"]["disks"][1]["serial"]),
                ("sdz", NEW_NAMES["storage"]["disks"][2]["serial"]),
            ],
            device_names,
        )

    def test_only_updates_physical_block_devices(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_ids_one = [
            device.id
            for device in PhysicalBlockDevice.objects.filter(node=node)
        ]
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_ids_two = [
            device.id
            for device in PhysicalBlockDevice.objects.filter(node=node)
        ]
        self.assertItemsEqual(created_ids_two, created_ids_one)

    def test_doesnt_reset_boot_disk(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        boot_disk = PhysicalBlockDevice.objects.filter(node=node).first()
        node.boot_disk = boot_disk
        node.save()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertEqual(boot_disk, reload_object(node).boot_disk)

    def test_clears_boot_disk(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        update_node_physical_block_devices(node, {}, create_numa_nodes(node))
        self.assertIsNone(reload_object(node).boot_disk)

    def test_creates_physical_block_devices_in_order(self):
        device_names = [
            device["id"] for device in SAMPLE_LXD_RESOURCES["storage"]["disks"]
        ]
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        created_names = [
            device.name
            for device in (
                PhysicalBlockDevice.objects.filter(node=node).order_by("id")
            )
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
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
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
        update_node_physical_block_devices(
            node, SAMPLE_LXD_DEFAULT_BLOCK_SIZE, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
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
        update_node_physical_block_devices(
            node, NO_DEVICE_PATH, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
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
        update_node_physical_block_devices(
            node, NO_SERIAL, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
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
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertEqual(
            0,
            PhysicalBlockDevice.objects.filter(node=other_node).count(),
            "Created physical block device for the incorrect node.",
        )

    def test_creates_physical_block_device_with_rotary_tag(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).last().tags,
            Contains("rotary"),
        )
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).last().tags,
            Not(Contains("ssd")),
        )

    def test_creates_physical_block_device_with_rotary_and_rpm_tags(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).last().tags,
            Contains("rotary"),
        )
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).last().tags,
            Contains("5400rpm"),
        )

    def test_creates_physical_block_device_with_ssd_tag(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            ContainsAll(["ssd"]),
        )
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains("rotary")),
        )

    def test_creates_physical_block_device_without_removable_tag(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains("removable")),
        )

    def test_creates_physical_block_device_with_removable_tag(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).last().tags,
            Contains("removable"),
        )

    def test_creates_physical_block_device_without_sata_tag(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).last().tags,
            Not(Contains("sata")),
        )

    def test_creates_physical_block_device_with_sata_tag(self):
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains("sata"),
        )

    def test_ignores_min_block_device_size_devices(self):
        UNDER_MIN_BLOCK_SIZE = deepcopy(SAMPLE_LXD_RESOURCES)
        UNDER_MIN_BLOCK_SIZE["storage"]["disks"][0]["size"] = random.randint(
            1, MIN_BLOCK_DEVICE_SIZE
        )
        UNDER_MIN_BLOCK_SIZE["storage"]["disks"][1]["size"] = random.randint(
            1, MIN_BLOCK_DEVICE_SIZE
        )
        node = factory.make_Node()
        update_node_physical_block_devices(
            node, UNDER_MIN_BLOCK_SIZE, create_numa_nodes(node)
        )
        self.assertEquals(
            0, len(PhysicalBlockDevice.objects.filter(node=node))
        )

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
        update_node_physical_block_devices(
            node, ONE_DISK, create_numa_nodes(node)
        )

        self.assertEquals(1, len(node.get_latest_testing_script_results))
        script_result = node.get_latest_testing_script_results.get(
            script=script
        )
        self.assertDictEqual(
            {
                "storage": {
                    "type": "storage",
                    "value": {
                        "id_path": "/dev/disk/by-id/wwn-0x12345",
                        "physical_blockdevice_id": (
                            node.physicalblockdevice_set.first().id
                        ),
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

        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        _, layout = get_applied_storage_layout_for_node(node)
        self.assertEquals(
            Config.objects.get_config("default_storage_layout"), layout
        )

    def test_doesnt_set_storage_layout_if_pod(self):
        pod = factory.make_Pod()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        pod.hints.nodes.add(node)
        mock_set_default_storage_layout = self.patch(
            node_module.Node, "set_default_storage_layout"
        )

        update_node_physical_block_devices(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        self.assertThat(mock_set_default_storage_layout, MockNotCalled())
        _, layout = get_applied_storage_layout_for_node(node)
        self.assertEquals("blank", layout)


class TestUpdateNodeNetworkInformation(MAASServerTestCase):
    """Tests the update_node_network_information function using data from LXD.

    The EXPECTED_MACS dictionary below must match the contents of the file,
    which should specify a list of physical interfaces (such as what would
    be expected to be found during commissioning).
    """

    EXPECTED_INTERFACES = {
        "eth0": MAC("00:00:00:00:00:01"),
        "eth1": MAC("00:00:00:00:00:02"),
        "eth2": MAC("00:00:00:00:00:03"),
    }

    EXPECTED_INTERFACES_XENIAL = {
        "ens3": MAC("52:54:00:2d:39:49"),
        "ens10": MAC("52:54:00:e5:c6:6b"),
        "ens11": MAC("52:54:00:ed:9f:9d"),
        "ens12": MAC("52:54:00:ed:9f:00"),
    }

    def assert_expected_interfaces_and_macs_exist_for_node(
        self, node, expected_interfaces=EXPECTED_INTERFACES
    ):
        """Asserts to ensure that the type, name, and MAC address are
        appropriate, given Node's interfaces. (and an optional list of
        expected interfaces which must exist)
        """
        node_interfaces = list(Interface.objects.filter(node=node))

        expected_interfaces = expected_interfaces.copy()

        self.assertThat(len(node_interfaces), Equals(len(expected_interfaces)))

        for interface in node_interfaces:
            if interface.name.startswith("eth") or interface.name.startswith(
                "ens"
            ):
                parts = interface.name.split(".")
                if len(parts) == 2 and parts[1].isdigit():
                    iftype = INTERFACE_TYPE.VLAN
                else:
                    iftype = INTERFACE_TYPE.PHYSICAL
                self.assertThat(interface.type, Equals(iftype))
            self.assertIn(interface.name, expected_interfaces)
            self.assertThat(
                interface.mac_address,
                Equals(expected_interfaces[interface.name]),
            )

    def test_does_nothing_if_skip_networking(self):
        node = factory.make_Node(interface=True, skip_networking=True)
        boot_interface = node.get_boot_interface()
        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assertIsNotNone(reload_object(boot_interface))
        self.assertFalse(reload_object(node).skip_networking)

    def test_does_nothing_if_duplicate_mac_on_controller(self):
        mock_iface_get = self.patch(
            hooks_module.PhysicalInterface.objects, "get"
        )
        rack = factory.make_RackController()
        create_IPADDR_OUTPUT_NAME_script(rack, IP_ADDR_OUTPUT)
        mac = factory.make_mac_address()
        duplicate_mac_lxd_resources = deepcopy(SAMPLE_LXD_RESOURCES)
        for card in duplicate_mac_lxd_resources["network"]["cards"]:
            for port in card["ports"]:
                port["address"] = mac
        update_node_network_information(
            rack, duplicate_mac_lxd_resources, create_numa_nodes(rack)
        )
        self.assertThat(mock_iface_get, MockNotCalled())

    def test_does_nothing_if_duplicate_mac_on_pod(self):
        mock_iface_get = self.patch(
            hooks_module.PhysicalInterface.objects, "get"
        )
        pod = factory.make_Pod()
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_empty_script_sets=True
        )
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        pod.hints.nodes.add(node)
        mac = factory.make_mac_address()
        duplicate_mac_lxd_resources = deepcopy(SAMPLE_LXD_RESOURCES)
        for card in duplicate_mac_lxd_resources["network"]["cards"]:
            for port in card["ports"]:
                port["address"] = mac
        update_node_network_information(
            node, duplicate_mac_lxd_resources, create_numa_nodes(node)
        )
        self.assertThat(mock_iface_get, MockNotCalled())

    def test_raises_exception_if_duplicate_mac_on_machine(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        mac = factory.make_mac_address()
        duplicate_mac_lxd_resources = deepcopy(SAMPLE_LXD_RESOURCES)
        for card in duplicate_mac_lxd_resources["network"]["cards"]:
            for port in card["ports"]:
                port["address"] = mac
        self.assertRaises(
            hooks_module.DuplicateMACs,
            update_node_network_information,
            node,
            duplicate_mac_lxd_resources,
            create_numa_nodes(node),
        )

    def test_add_all_interfaces(self):
        """Test a node that has no previously known interfaces on which we
        need to add a series of interfaces.
        """
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()
        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_interfaces_for_all_ports(self):
        """Interfaces are created for all ports in a network card."""
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # all ports belong to a single card
        lxd_output = deepcopy(SAMPLE_LXD_RESOURCES)
        card0 = lxd_output["network"]["cards"][0]
        port1 = lxd_output["network"]["cards"][1]["ports"][0]
        port2 = lxd_output["network"]["cards"][2]["ports"][0]
        port1["port"] = 1
        port2["port"] = 2
        card0["ports"].extend([port1, port2])
        # remove other cards
        del lxd_output["network"]["cards"][1:]

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()
        update_node_network_information(
            node, lxd_output, create_numa_nodes(node)
        )

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_add_all_interfaces_xenial(self):
        """Test a node that has no previously known interfaces on which we
        need to add a series of interfaces.
        """
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT_XENIAL)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_RESOURCES)
        XENIAL_NETWORK["network"] = SAMPLE_LXD_XENIAL_NETWORK
        update_node_network_information(
            node, XENIAL_NETWORK, create_numa_nodes(node)
        )

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(
            node, expected_interfaces=self.EXPECTED_INTERFACES_XENIAL
        )

    def test_adds_vendor_info(self):
        """Vendor, product and firmware version details are added."""
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        nic = Interface.objects.get(mac_address="00:00:00:00:00:01")
        self.assertEqual(nic.vendor, "Intel Corporation")
        self.assertEqual(nic.product, "Ethernet Connection I217-LM")
        self.assertEqual(nic.firmware_version, "1.2.3.4")

    def test_adds_sriov_info(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        nic = Interface.objects.get(mac_address="00:00:00:00:00:01")
        self.assertEqual(nic.sriov_max_vf, 8)

    def test_adds_sriov_tag_if_sriov(self):
        node = factory.make_Node()

        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
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
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        resources["network"]["cards"].append(
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
        update_node_network_information(
            node, resources, create_numa_nodes(node)
        )
        self.assertFalse(
            Interface.objects.filter(mac_address="01:01:01:01:01:01").exists()
        )

    def test_adds_ifaces_under_sriov_if_not_deployed(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        resources = deepcopy(SAMPLE_LXD_RESOURCES)
        resources["network"]["cards"].append(
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
        update_node_network_information(
            node, resources, create_numa_nodes(node)
        )
        nic = Interface.objects.get(mac_address="01:01:01:01:01:01")
        self.assertEqual(nic.vendor, "Cavium, Inc.")

    def test_ignores_missing_vendor_data(self):
        """Test a node that has no previously known interfaces gets info from
        lshw added.
        """
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        lxd_output = deepcopy(SAMPLE_LXD_RESOURCES)
        card_info = lxd_output["network"]["cards"][0]
        del card_info["vendor"]
        del card_info["product"]
        del card_info["firmware_version"]
        update_node_network_information(
            node, lxd_output, create_numa_nodes(node)
        )

        nic = Interface.objects.get(mac_address="00:00:00:00:00:01")
        self.assertIsNone(nic.vendor)
        self.assertIsNone(nic.product)
        self.assertIsNone(nic.firmware_version)

    def test_one_mac_missing(self):
        """Test whether we correctly detach a NIC that no longer appears to be
        connected to the node.
        """
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        # Create a MAC address that we know is not in the test dataset.
        factory.make_Interface(node=node, mac_address="01:23:45:67:89:ab")

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        # These should have been added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

        # This one should have been removed because it no longer shows on the
        # `ip addr` output.
        db_macaddresses = [
            iface.mac_address for iface in node.interface_set.all()
        ]
        self.assertNotIn(MAC("01:23:45:67:89:ab"), db_macaddresses)

    def test_reassign_mac(self):
        """Test whether we can assign a MAC address previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()

        # Create a MAC address that we know IS in the test dataset.
        interface_to_be_reassigned = factory.make_Interface(node=node1)
        interface_to_be_reassigned.mac_address = MAC("00:00:00:00:00:01")
        interface_to_be_reassigned.save()

        node2 = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node2, IP_ADDR_OUTPUT)
        update_node_network_information(
            node2, SAMPLE_LXD_RESOURCES, create_numa_nodes(node2)
        )

        self.assert_expected_interfaces_and_macs_exist_for_node(node2)

        # Ensure the MAC object moved over to node2.
        self.assertItemsEqual([], Interface.objects.filter(node=node1))
        self.assertItemsEqual([], Interface.objects.filter(node=node1))

    def test_reassign_interfaces(self):
        """Test whether we can assign interfaces previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node1, IP_ADDR_OUTPUT)

        update_node_network_information(
            node1, SAMPLE_LXD_RESOURCES, create_numa_nodes(node1)
        )

        # First make sure the first node has all the expected interfaces.
        self.assert_expected_interfaces_and_macs_exist_for_node(node1)

        # Grab the id from one of the created interfaces.
        interface_id = Interface.objects.filter(node=node1).first().id

        # Now make sure the second node has them all.
        node2 = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node2, IP_ADDR_OUTPUT)
        update_node_network_information(
            node2, SAMPLE_LXD_RESOURCES, create_numa_nodes(node2)
        )

        self.assert_expected_interfaces_and_macs_exist_for_node(node2)

        # Now make sure all the objects moved to the second node.
        self.assertItemsEqual([], Interface.objects.filter(node=node1))
        self.assertItemsEqual([], Interface.objects.filter(node=node1))

        # ... and ensure that the interface was deleted.
        self.assertItemsEqual([], Interface.objects.filter(id=interface_id))

    def test_deletes_virtual_interfaces_with_shared_mac(self):
        # Note: since this VLANInterface will be linked to the default VLAN
        # ("vid 0", which is actually invalid) the VLANInterface will
        # automatically get the name "vlan0".
        ETH0_MAC = self.EXPECTED_INTERFACES["eth0"].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES["eth1"].get_raw()
        BOND_NAME = "bond0"
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        eth0 = factory.make_Interface(
            name="eth0", mac_address=ETH0_MAC, node=node
        )
        eth1 = factory.make_Interface(
            name="eth1", mac_address=ETH1_MAC, node=node
        )

        factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            mac_address=ETH0_MAC,
            parents=[eth0],
            node=node,
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            mac_address=ETH1_MAC,
            parents=[eth1],
            node=node,
            name=BOND_NAME,
        )

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_interface_name_changed(self):
        ETH0_MAC = self.EXPECTED_INTERFACES["eth1"].get_raw()
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            mac_address=ETH0_MAC,
            node=node,
        )
        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        # This will ensure that the interface was renamed appropriately.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_mac_id_is_preserved(self):
        """Test whether MAC address entities are preserved and not recreated"""
        ETH0_MAC = self.EXPECTED_INTERFACES["eth0"].get_raw()
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        iface_to_be_preserved = factory.make_Interface(
            mac_address=ETH0_MAC, node=node
        )

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        self.assertIsNotNone(reload_object(iface_to_be_preserved))

    def test_legacy_model_upgrade_preserves_interfaces(self):
        ETH0_MAC = self.EXPECTED_INTERFACES["eth0"].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES["eth1"].get_raw()
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(mac_address=ETH1_MAC, node=node)
        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        self.assertEqual(eth0, Interface.objects.get(id=eth0.id))
        self.assertEqual(eth1, Interface.objects.get(id=eth1.id))

        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_legacy_model_with_extra_mac(self):
        ETH0_MAC = self.EXPECTED_INTERFACES["eth0"].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES["eth1"].get_raw()
        ETH2_MAC = self.EXPECTED_INTERFACES["eth2"].get_raw()
        ETH3_MAC = "00:00:00:00:01:04"
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(mac_address=ETH1_MAC, node=node)
        eth2 = factory.make_Interface(mac_address=ETH2_MAC, node=node)
        eth3 = factory.make_Interface(mac_address=ETH3_MAC, node=node)

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        self.assert_expected_interfaces_and_macs_exist_for_node(node)

        # Make sure we re-used the existing MACs in the database.
        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNotNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(eth2))

        # Make sure the interface that no longer exists has been removed.
        self.assertIsNone(reload_object(eth3))

    def test_deletes_virtual_interfaces_with_unique_mac(self):
        ETH0_MAC = self.EXPECTED_INTERFACES["eth0"].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES["eth1"].get_raw()
        BOND_MAC = "00:00:00:00:01:02"
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(mac_address=ETH1_MAC, node=node)
        factory.make_Interface(INTERFACE_TYPE.VLAN, node=node, parents=[eth0])
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            mac_address=BOND_MAC,
            node=node,
            parents=[eth1],
        )

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_deletes_virtual_interfaces_linked_to_removed_macs(self):
        VLAN_MAC = "00:00:00:00:01:01"
        BOND_MAC = "00:00:00:00:01:02"
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
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
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test_creates_discovered_ip_address(self):
        node = factory.make_Node()
        cidr = "192.168.0.3/24"
        subnet = factory.make_Subnet(
            cidr=cidr, vlan=VLAN.objects.get_default_vlan()
        )
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        eth0 = Interface.objects.get(node=node, name="eth0")
        address = str(IPNetwork(cidr).ip)
        ipv4_ip = eth0.ip_addresses.get(ip=address)
        self.assertThat(
            ipv4_ip,
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet, ip=address
            ),
        )

    def test_creates_discovered_ip_address_on_xenial(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT_XENIAL)
        cidr = "172.16.100.108/24"
        subnet = factory.make_Subnet(
            cidr=cidr, vlan=VLAN.objects.get_default_vlan()
        )
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_RESOURCES)
        XENIAL_NETWORK["network"] = SAMPLE_LXD_XENIAL_NETWORK
        update_node_network_information(
            node, XENIAL_NETWORK, create_numa_nodes(node)
        )
        ens3 = Interface.objects.get(node=node, name="ens3")
        address = str(IPNetwork(cidr).ip)
        ipv4_ip = ens3.ip_addresses.get(ip=address)
        self.assertThat(
            ipv4_ip,
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet, ip=address
            ),
        )
        # First IP is DISCOVERED second is AUTO configured.
        self.assertThat(ens3.ip_addresses.count(), Equals(2))

    def test_handles_disconnected_interfaces(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT_XENIAL)
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_RESOURCES)
        XENIAL_NETWORK["network"] = SAMPLE_LXD_XENIAL_NETWORK
        update_node_network_information(
            node, XENIAL_NETWORK, create_numa_nodes(node)
        )
        ens12 = Interface.objects.get(node=node, name="ens12")
        self.assertThat(ens12.vlan, Is(None))

    def test_disconnects_previously_connected_interface(self):
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT_XENIAL)
        subnet = factory.make_Subnet()
        ens12 = factory.make_Interface(
            name="ens12",
            node=node,
            mac_address="52:54:00:ed:9f:00",
            subnet=subnet,
        )
        self.assertThat(ens12.vlan, Equals(subnet.vlan))
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_RESOURCES)
        XENIAL_NETWORK["network"] = SAMPLE_LXD_XENIAL_NETWORK
        update_node_network_information(
            node, XENIAL_NETWORK, create_numa_nodes(node)
        )
        ens12 = Interface.objects.get(node=node, name="ens12")
        self.assertThat(ens12.vlan, Is(None))

    def test_ignores_openbmc_interface(self):
        """Ensure that OpenBMC interface is ignored."""
        node = factory.make_Node()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        SWITCH_OPENBMC_MAC_JSON = deepcopy(SAMPLE_LXD_RESOURCES)
        SWITCH_OPENBMC_MAC_JSON["network"]["cards"][0]["ports"][0][
            "address"
        ] = SWITCH_OPENBMC_MAC

        update_node_network_information(
            node, SWITCH_OPENBMC_MAC_JSON, create_numa_nodes(node)
        )

        # Specifically, there is no OpenBMC interface with a fixed MAC address.
        node_interfaces = Interface.objects.filter(node=node)
        all_macs = [interface.mac_address for interface in node_interfaces]
        self.assertNotIn(SWITCH_OPENBMC_MAC, all_macs)

    def test_sets_boot_interface(self):
        """Test a node will have its boot_interface set if none are defined."""
        subnet = factory.make_Subnet(cidr="192.168.0.3/24")
        node = factory.make_Node()

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()
        node.boot_interface = None
        node.boot_cluster_ip = "192.168.0.1"
        node.save()
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )
        node = reload_object(node)

        self.assertIsNotNone(
            node.boot_interface.vlan.subnet_set.filter(id=subnet.id).first()
        )

    def test_regenerates_testing_script_set(self):
        factory.make_Subnet(cidr="192.168.0.3/24")
        node = factory.make_Node(boot_cluster_ip="192.168.0.1")
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)
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
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        self.assertEquals(1, len(node.get_latest_testing_script_results))
        # The default network layout only configures the boot interface.
        script_result = node.get_latest_testing_script_results.get(
            script=script
        )
        self.assertDictEqual(
            {
                "interface": {
                    "type": "interface",
                    "value": {
                        "name": node.boot_interface.name,
                        "mac_address": str(node.boot_interface.mac_address),
                        "vendor": node.boot_interface.vendor,
                        "product": node.boot_interface.product,
                        "interface_id": node.boot_interface.id,
                    },
                }
            },
            script_result.parameters,
        )

    def test_sets_default_configuration(self):
        factory.make_Subnet(cidr="192.168.0.3/24")
        node = factory.make_Node(boot_cluster_ip="192.168.0.1")
        create_IPADDR_OUTPUT_NAME_script(node, IP_ADDR_OUTPUT)

        update_node_network_information(
            node, SAMPLE_LXD_RESOURCES, create_numa_nodes(node)
        )

        # 2 devices configured, one for IPv4 one for IPv6.
        self.assertEquals(
            2,
            node.interface_set.filter(
                ip_addresses__alloc_type=IPADDRESS_TYPE.AUTO
            ).count(),
        )


class TestUpdateBootInterface(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.hook = NODE_INFO_SCRIPTS[KERNEL_CMDLINE_OUTPUT_NAME]["hook"]

    def test_sets_boot_interface_bootif(self):
        node = factory.make_Node()
        Interface.objects.filter(node_id=node.id).delete()
        nic1 = factory.make_Interface(node=node)
        nic2 = factory.make_Interface(node=node)
        kernel_cmdline1 = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(nic1.mac_address).replace(":", "-")
        )
        kernel_cmdline2 = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(nic2.mac_address).replace(":", "-")
        )

        self.hook(node, kernel_cmdline1.encode("utf-8"), 0)
        node = reload_object(node)
        self.assertEqual(nic1, node.boot_interface)

        self.hook(node, kernel_cmdline2.encode("utf-8"), 0)
        node = reload_object(node)
        self.assertEqual(nic2, node.boot_interface)

    def test_boot_interface_bootif_no_such_mac(self):
        node = factory.make_Node()
        Interface.objects.filter(node_id=node.id).delete()
        kernel_cmdline = KERNEL_CMDLINE_OUTPUT.format(
            mac_address="11-22-33-44-55-66"
        )
        logger = self.useFixture(FakeLogger())

        self.hook(node, kernel_cmdline.encode("utf-8"), 0)
        node = reload_object(node)

        self.assertIn(
            "BOOTIF interface 11:22:33:44:55:66 doesn't exist", logger.output
        )

    def test_no_bootif(self):
        node = factory.make_Node()
        Interface.objects.filter(node_id=node.id).delete()
        nic = factory.make_Interface(node=node)
        node.boot_interface = nic
        node.save()

        self.hook(node, b"no bootif mac", 0)
        node = reload_object(node)

        self.assertEqual(nic, node.boot_interface)

    def test_non_zero_exit_status(self):
        node = factory.make_Node()
        Interface.objects.filter(node_id=node.id).delete()
        nic = factory.make_Interface(node=node)
        node.boot_interface = None
        node.save()
        kernel_cmdline = KERNEL_CMDLINE_OUTPUT.format(
            mac_address=str(nic.mac_address).replace(":", "-")
        )

        logger = self.useFixture(FakeLogger())
        self.hook(node, kernel_cmdline.encode("utf-8"), 1)
        node = reload_object(node)
        self.assertIsNone(node.boot_interface)

        self.assertIn("kernel-cmdline failed with status: 1", logger.output)


class TestParseBootifCmdline(MAASTestCase):
    def test_normal(self):
        mac_address = "01:02:03:04:05:06"
        self.assertEqual(
            mac_address,
            parse_bootif_cmdline(
                KERNEL_CMDLINE_OUTPUT.format(
                    mac_address=mac_address.replace(":", "-")
                )
            ),
        )

    def test_garbage(self):
        self.assertIsNone(parse_bootif_cmdline("garbage"))

    def test_garbage_bootif(self):
        self.assertIsNone(parse_bootif_cmdline("BOOTIF=garbage"))

    def test_bootif_too_few(self):
        self.assertIsNone(parse_bootif_cmdline("BOOTIF=01-02-03-04-05-06"))
