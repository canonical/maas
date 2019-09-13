# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test hooks."""

__all__ = []

from copy import deepcopy
import doctest
import json
import os.path
import random
from textwrap import dedent

from fixtures import FakeLogger
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_METADATA,
)
from maasserver.fields import MAC
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.config import Config
from maasserver.models.interface import Interface
from maasserver.models.nodemetadata import NodeMetadata
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.switch import Switch
from maasserver.models.tag import Tag
from maasserver.models.vlan import VLAN
from maasserver.storage_layouts import get_applied_storage_layout_for_node
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.hooks import (
    add_switch,
    add_switch_vendor_model_tags,
    create_metadata_by_modalias,
    detect_switch_vendor_model,
    determine_hardware_matches,
    extract_router_mac_addresses,
    filter_modaliases,
    get_dmi_data,
    process_lxd_results,
    retag_node_for_hardware_by_modalias,
    set_virtual_tag,
    SWITCH_OPENBMC_MAC,
    update_hardware_details,
    update_node_fruid_metadata,
    update_node_network_information,
    update_node_network_interface_tags,
    update_node_physical_block_devices,
)
import metadataserver.builtin_scripts.hooks as hooks_module
from metadataserver.enum import (
    SCRIPT_STATUS,
    SCRIPT_TYPE,
)
from metadataserver.models import ScriptSet
from netaddr import IPNetwork
from provisioningserver.refresh.node_info_scripts import (
    IPADDR_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)
from testtools.matchers import (
    Contains,
    ContainsAll,
    DocTestMatches,
    Equals,
    Is,
    MatchesStructure,
    Not,
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


SAMPLE_LXD_JSON = {
    "cpu": {
        "architecture": "x86_64",
        "sockets": [
            {
                "name": "Intel(R) Core(TM) i7-4700MQ CPU @ 2.40GHz",
                "vendor": "GenuineIntel",
                "socket": 0,
                "cache": [
                    {
                        "level": 1,
                        "type": "Data",
                        "size": 32768
                    },
                    {
                        "level": 1,
                        "type": "Instruction",
                        "size": 32768
                    },
                    {
                        "level": 2,
                        "type": "Unified",
                        "size": 262144
                    },
                    {
                        "level": 3,
                        "type": "Unified",
                        "size": 6291456
                    }
                ],
                "cores": [
                    {
                        "core": 0,
                        "numa_node": 0,
                        "threads": [
                            {
                                "id": 0,
                                "thread": 0,
                                "online": True
                            },
                            {
                                "id": 1,
                                "thread": 1,
                                "online": True
                            }
                        ],
                        "frequency": 3247
                    },
                    {
                        "core": 1,
                        "numa_node": 0,
                        "threads": [
                            {
                                "id": 2,
                                "thread": 0,
                                "online": True
                            },
                            {
                                "id": 3,
                                "thread": 1,
                                "online": True
                            }
                        ],
                        "frequency": 3192
                    },
                    {
                        "core": 2,
                        "numa_node": 0,
                        "threads": [
                            {
                                "id": 4,
                                "thread": 0,
                                "online": True
                            },
                            {
                                "id": 5,
                                "thread": 1,
                                "online": True
                            }
                        ],
                        "frequency": 3241
                    },
                    {
                        "core": 3,
                        "numa_node": 0,
                        "threads": [
                            {
                                "id": 6,
                                "thread": 0,
                                "online": True
                            },
                            {
                                "id": 7,
                                "thread": 1,
                                "online": True
                            }
                        ],
                        "frequency": 3247
                    }
                ],
                "frequency": 3231,
                "frequency_minimum": 800,
                "frequency_turbo": 3400
            }
        ],
        "total": 8
    },
    "memory": {
        "nodes": [
            {
                "numa_node": 0,
                "hugepages_used": 0,
                "hugepages_total": 0,
                "used": 16430092288,
                "total": 16691519488
            }
        ],
        "hugepages_total": 0,
        "hugepages_used": 0,
        "hugepages_size": 2097152,
        "used": 12116492288,
        "total": 16691519488
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
                    "render_device": "226:128"
                },
                "numa_node": 0,
                "pci_address": "0000:00:02.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": (
                    "4th Gen Core Processor Integrated Graphics Controller"),
                "product_id": "0416"
            }
        ],
        "total": 1
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
                            "1000baseT/Full"
                        ],
                        "supported_ports": [
                            "twisted pair"
                        ],
                        "port_type": "twisted pair",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": True,
                        "link_speed": 1000
                    }
                ],
                "numa_node": 0,
                "pci_address": "0000:00:19.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "Ethernet Connection I217-LM",
                "product_id": "153a"
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
                            "1000baseT/Full"
                        ],
                        "supported_ports": [
                            "twisted pair"
                        ],
                        "port_type": "twisted pair",
                        "transceiver_type": "internal",
                        "auto_negotiation": True,
                        "link_detected": False
                    }
                ],
                "numa_node": 0,
                "pci_address": "0000:00:19.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "Ethernet Connection I217-LM",
                "product_id": "153a"
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
                        "link_detected": True
                    }
                ],
                "numa_node": 0,
                "pci_address": "0000:04:00.0",
                "vendor": "Intel Corporation",
                "vendor_id": "8086",
                "product": "Wireless 7260",
                "product_id": "08b2"
            }
        ],
        "total": 3
    },
    "storage": {
        "disks": [
            {
                "id": "sda",
                "device": "8:0",
                "model": "Crucial_CT512M55",
                "type": "scsi",
                "read_only": False,
                "size": 512110190592,
                "removable": False,
                "numa_node": 0,
                "partitions": [
                    {
                        "id": "sda1",
                        "device": "8:1",
                        "read_only": False,
                        "size": 536870912,
                        "partition": 1
                    },
                    {
                        "id": "sda2",
                        "device": "8:2",
                        "read_only": False,
                        "size": 511705088,
                        "partition": 2
                    },
                    {
                        "id": "sda3",
                        "device": "8:3",
                        "read_only": False,
                        "size": 511060213760,
                        "partition": 3
                    }
                ]
            },
            {
                "id": "sr0",
                "device": "11:0",
                "model": "DVD-RAM UJ8E2",
                "type": "scsi",
                "read_only": False,
                "size": 1073741312,
                "removable": True,
                "numa_node": 0,
                "partitions": []
            }
        ],
        "total": 5
    }
}


# This matches ip_addr_results_xenial.txt for the unit tests
SAMPLE_LXD_XENIAL_NETWORK_JSON = {
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
                        "1000baseT/Full"
                    ],
                    "supported_ports": [
                        "twisted pair"
                    ],
                    "port_type": "twisted pair",
                    "transceiver_type": "internal",
                    "auto_negotiation": True,
                    "link_detected": True,
                    "link_speed": 1000
                }
            ],
            "numa_node": 0,
            "pci_address": "0000:00:19.0",
            "vendor": "Intel Corporation",
            "vendor_id": "8086",
            "product": "Ethernet Connection I217-LM",
            "product_id": "153a"
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
                        "1000baseT/Full"
                    ],
                    "supported_ports": [
                        "twisted pair"
                    ],
                    "port_type": "twisted pair",
                    "transceiver_type": "internal",
                    "auto_negotiation": True,
                    "link_detected": False
                }
            ],
            "numa_node": 0,
            "pci_address": "0000:00:19.0",
            "vendor": "Intel Corporation",
            "vendor_id": "8086",
            "product": "Ethernet Connection I217-LM",
            "product_id": "153a"
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
                    "link_detected": False
                }
            ],
            "numa_node": 0,
            "pci_address": "0000:04:00.0",
            "vendor": "Intel Corporation",
            "vendor_id": "8086",
            "product": "Wireless 7260",
            "product_id": "08b2"
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
                    "link_detected": False
                }
            ],
            "numa_node": 0,
            "pci_address": "0000:04:00.0",
            "vendor": "Intel Corporation",
            "vendor_id": "8086",
            "product": "Wireless 7260",
            "product_id": "08b2"
        }
    ],
    "total": 4
}


def make_lldp_output(macs):
    """Return an example raw lldp output containing the given MACs."""
    interfaces = '\n'.join(
        lldp_output_interface_template % mac
        for mac in macs
        )
    script = (lldp_output_template % interfaces).encode('utf8')
    return bytes(script)


class TestExtractRouters(MAASServerTestCase):

    def test_extract_router_mac_addresses_returns_None_when_empty_input(self):
        self.assertIsNone(extract_router_mac_addresses(''))

    def test_extract_router_mac_addresses_returns_empty_list(self):
        lldp_output = make_lldp_output([])
        self.assertItemsEqual([], extract_router_mac_addresses(lldp_output))

    def test_extract_router_mac_addresses_returns_routers_list(self):
        macs = ["11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"]
        lldp_output = make_lldp_output(macs)
        routers = extract_router_mac_addresses(lldp_output)
        self.assertItemsEqual(macs, routers)


class TestSetVirtualTag(MAASServerTestCase):

    def getVirtualTag(self):
        virtual_tag, _ = Tag.objects.get_or_create(name='virtual')
        return virtual_tag

    def assertTagsEqual(self, node, tags):
        self.assertItemsEqual(
            tags, [tag.name for tag in node.tags.all()])

    def test_sets_virtual_tag(self):
        node = factory.make_Node()
        self.assertTagsEqual(node, [])
        set_virtual_tag(node, b"qemu", 0)
        self.assertTagsEqual(node, ["virtual"])

    def test_removes_virtual_tag(self):
        node = factory.make_Node()
        node.tags.add(self.getVirtualTag())
        self.assertTagsEqual(node, ["virtual"])
        set_virtual_tag(node, b"none", 0)
        self.assertTagsEqual(node, [])

    def test_output_not_containing_virtual_does_not_set_tag(self):
        logger = self.useFixture(FakeLogger())
        node = factory.make_Node()
        self.assertTagsEqual(node, [])
        set_virtual_tag(node, b"", 0)
        self.assertTagsEqual(node, [])
        self.assertIn(
            "No virtual type reported in VIRTUALITY_SCRIPT output for node "
            "%s" % node.system_id, logger.output)

    def test_output_not_containing_virtual_does_not_remove_tag(self):
        logger = self.useFixture(FakeLogger())
        node = factory.make_Node()
        node.tags.add(self.getVirtualTag())
        self.assertTagsEqual(node, ["virtual"])
        set_virtual_tag(node, b"", 0)
        self.assertTagsEqual(node, ["virtual"])
        self.assertIn(
            "No virtual type reported in VIRTUALITY_SCRIPT output for node "
            "%s" % node.system_id, logger.output)


class TestDetectSwitchVendorModelDMIScenarios(MAASServerTestCase):

    scenarios = (
        ('accton_wedge40_1', {
            'modaliases': [
                "dmi:svnIntel:pnEPGSVR"
            ],
            'dmi_data': frozenset({
                'svnIntel',
                'pnEPGSVR',
            }),
            'result': ('accton', 'wedge40')
        }),
        ('accton_wedge40_2', {
            'modaliases': [
                "dmi:svnJoytech:pnWedge-AC-F20-001329"
            ],
            'dmi_data': frozenset({
                'svnJoytech',
                'pnWedge-AC-F20-001329',
            }),
            'result': ('accton', 'wedge40')
        }),
        ('accton_wedge100', {
            'modaliases': [
                "dmi:svnTobefilledbyO.E.M.:pnTobefilledbyO.E.M.:"
                "rnPCOM-B632VG-ECC-FB-ACCTON-D"
            ],
            'dmi_data': frozenset({
                'svnTobefilledbyO.E.M.',
                'pnTobefilledbyO.E.M.',
                'rnPCOM-B632VG-ECC-FB-ACCTON-D',
            }),
            'result': ('accton', 'wedge100')
        }),
        ('mellanox_sn2100', {
            'modaliases': [
                'dmi:svnMellanoxTechnologiesLtd.:pn"MSN2100-CB2FO"'
            ],
            'dmi_data': frozenset({
                'svnMellanoxTechnologiesLtd.',
                'pn"MSN2100-CB2FO"',
            }),
            'result': ('mellanox', 'sn2100')
        }),
    )

    def test__detect_switch_vendor_model(self):
        detected = detect_switch_vendor_model(self.dmi_data)
        self.assertThat(detected, Equals(self.result))

    def test__get_dmi_data(self):
        dmi_data = get_dmi_data(self.modaliases)
        self.assertThat(dmi_data, Equals(self.dmi_data))


class TestDetectSwitchVendorModel(MAASServerTestCase):

    def test__detect_switch_vendor_model_returns_none_by_default(self):
        detected = detect_switch_vendor_model(set())
        self.assertThat(detected, Equals((None, None)))


TEST_MODALIASES = [
    'pci:v00001A03d00001150sv000015D9sd00000888bc06sc04i00',
    'pci:v00001A03d00002000sv000015D9sd00000888bc03sc00i00',
    'pci:v00008086d00001533sv000015D9sd00001533bc02sc00i00',
    'pci:v00008086d000015B7sv000015D9sd000015B7bc02sc00i00',
    'pci:v00008086d00001918sv000015D9sd00000888bc06sc00i00',
    'pci:v00008086d0000A102sv000015D9sd00000888bc01sc06i01',
    'pci:v00008086d0000A118sv000015D9sd00000888bc06sc04i00',
    'pci:v00008086d0000A119sv000015D9sd00000888bc06sc04i00',
    'pci:v00008086d0000A11Asv000015D9sd00000888bc06sc04i00',
    'pci:v00008086d0000A121sv000015D9sd00000888bc05sc80i00',
    'pci:v00008086d0000A123sv000015D9sd00000888bc0Csc05i00',
    'pci:v00008086d0000A12Fsv000015D9sd00000888bc0Csc03i30',
    'pci:v00008086d0000A131sv000015D9sd00000888bc11sc80i00',
    'pci:v00008086d0000A13Dsv000015D9sd00000888bc07sc00i02',
    'pci:v00008086d0000A149sv000015D9sd00000888bc06sc01i00',
    'pci:v00008086d0000A170sv000015D9sd00000888bc04sc03i00',
    'usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip01in00',
    'usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip02in01',
    'usb:v0557p7000d0000dc09dsc00dp01ic09isc00ip00in00',
    'usb:v174Cp07D1d1000dc00dsc00dp00ic08isc06ip50in00',
    'usb:v1D6Bp0002d0410dc09dsc00dp01ic09isc00ip00in00',
    'usb:v1D6Bp0003d0410dc09dsc00dp03ic09isc00ip00in00',
]


class TestFilterModaliases(MAASTestCase):

    scenarios = (
        ('modalias_wildcard_multiple_match', {
            'modaliases': [
                "os:vendorCanonical:productUbuntu:version14.04",
                "beverage:typeCoffee:variantEspresso",
                "beverage:typeCoffee:variantCappuccino",
                "beverage:typeTea:variantProperBritish",
            ],
            'candidates': [
                'beverage:typeCoffee:*',
            ],
            'pci': None,
            'usb': None,
            'result': [
                "beverage:typeCoffee:variantEspresso",
                "beverage:typeCoffee:variantCappuccino",
            ]
        }),
        ('modalias_multiple_wildcard_match', {
            'modaliases': [
                "os:vendorCanonical:productUbuntu:version14.04",
                "beverage:typeCoffee:variantEspresso",
                "beverage:typeCoffee:variantCappuccino",
                "beverage:typeTea:variantProperBritish",
            ],
            'candidates': [
                'os:vendorCanonical:*',
                'os:*:productUbuntu:*',
                'beverage:*ProperBritish'
            ],
            'pci': None,
            'usb': None,
            'result': [
                "os:vendorCanonical:productUbuntu:version14.04",
                "beverage:typeTea:variantProperBritish",
            ]
        }),
        ('modalias_exact_match', {
            'modaliases': [
                "os:vendorCanonical:productUbuntu:version14.04",
                "beverage:typeCoffee:variantEspresso",
                "beverage:typeCoffee:variantCappuccino",
                "beverage:typeTea:variantProperBritish",
            ],
            'candidates': [
                'os:vendorCanonical:productUbuntu:version14.04',
            ],
            'pci': None,
            'usb': None,
            'result': [
                "os:vendorCanonical:productUbuntu:version14.04",
            ]
        }),
        ('pci_malformed_string', {
            'modaliases': TEST_MODALIASES,
            'candidates': None,
            'pci': [
                "8086"
            ],
            'usb': None,
            'result': []
        }),
        ('pci_exact_match', {
            'modaliases': TEST_MODALIASES,
            'candidates': None,
            'pci': [
                "8086:1918"
            ],
            'usb': None,
            'result': [
                "pci:v00008086d00001918sv000015D9sd00000888bc06sc00i00",
            ]
        }),
        ('pci_wildcard_match', {
            'modaliases': TEST_MODALIASES,
            'candidates': None,
            'pci': [
                "1a03:*"
            ],
            'usb': None,
            'result': [
                'pci:v00001A03d00001150sv000015D9sd00000888bc06sc04i00',
                'pci:v00001A03d00002000sv000015D9sd00000888bc03sc00i00',
            ]
        }),
        ('usb_malformed_string', {
            'modaliases': TEST_MODALIASES,
            'candidates': None,
            'pci': None,
            'usb': [
                "174c"
            ],
            'result': []
        }),
        ('usb_exact_match', {
            'modaliases': TEST_MODALIASES,
            'candidates': None,
            'pci': None,
            'usb': [
                "174c:07d1"
            ],
            'result': [
                'usb:v174Cp07D1d1000dc00dsc00dp00ic08isc06ip50in00',
            ]
        }),
        ('usb_wildcard_match', {
            'modaliases': TEST_MODALIASES,
            'candidates': None,
            'pci': None,
            'usb': [
                "0557:*"
            ],
            'result': [
                'usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip01in00',
                'usb:v0557p2419d0100dc00dsc00dp00ic03isc01ip02in01',
                'usb:v0557p7000d0000dc09dsc00dp01ic09isc00ip00in00'
            ]
        }),
    )

    def test__filter_modaliases(self):
        matches = filter_modaliases(
            self.modaliases, self.candidates, pci=self.pci, usb=self.usb)
        self.assertThat(matches, Equals(self.result))


class TestDetectHardware(MAASServerTestCase):

    scenarios = (
        ('caffeine_fueled_ubuntu_classic', {
            'modaliases': [
                "os:vendorCanonical:productUbuntu:version14.04",
                "beverage:typeCoffee:variantEspresso",
                "beverage:typeCoffee:variantCappuccino",
                "beverage:typeTea:variantProperBritish",
            ],
            'expected_match_indexes': [0, 1, 2],
            'expected_ruled_out_indexes': [3],
        }),
        ('caffeine_fueled_ubuntu_core', {
            'modaliases': [
                "os:vendorCanonical:productUbuntuCore:version16.04",
                "beverage:typeCoffee:variantEspresso",
                "beverage:typeCoffee:variantCappuccino",
                "beverage:typeTea:variantProperBritish",
            ],
            'expected_match_indexes': [0, 1, 3],
            'expected_ruled_out_indexes': [2],
        }),
        ('ubuntu_classic', {
            'modaliases': [
                "os:vendorCanonical:productUbuntu:version14.04",
            ],
            'expected_match_indexes': [1, 2],
            'expected_ruled_out_indexes': [0, 3],
        }),
        ('ubuntu_core', {
            'modaliases': [
                "os:vendorCanonical:productUbuntuCore:version16.04",
            ],
            'expected_match_indexes': [1, 3],
            'expected_ruled_out_indexes': [0, 2],
        }),
        ('none_of_the_above', {
            'modaliases': [
                "xos:vendorCanonical:productUbuntuCore:version16.04",
                "xbeverage:typeCoffee:variantEspresso",
                "xbeverage:typeCoffee:variantCappuccino",
                "xbeverage:typeTea:variantProperBritish",
            ],
            'expected_match_indexes': [],
            'expected_ruled_out_indexes': [0, 1, 2, 3],
        }),

    )

    hardware_database = [
        {
            'modaliases': [
                'beverage:typeCoffee:*',
                'beverage:typeTea:*',
            ],
            'tag': 'caffeine-fueled-sprint',
            'comment': "Caffeine-fueled sprint."
        },
        {
            'modaliases': [
                'os:vendorCanonical:productUbuntu*',
            ],
            'tag': 'ubuntu',
            'comment': "Ubuntu"
        },
        {
            'modaliases': [
                'os:vendorCanonical:productUbuntu:*',
            ],
            'tag': 'ubuntu-classic',
            'comment': "Ubuntu Classic"
        },
        {
            'modaliases': [
                'os:vendorCanonical:productUbuntuCore:*',
            ],
            'tag': 'ubuntu-core',
            'comment': "Ubuntu Core"
        },
    ]

    def test__determine_hardware_matches(self):
        discovered, ruled_out = determine_hardware_matches(
            self.modaliases, self.hardware_database)
        expected_matches = [
            self.hardware_database[index].copy()
            for index in self.expected_match_indexes
        ]
        # Note: determine_hardware_matches() adds the matches as informational.
        for item in discovered:
            self.expectThat(item['matches'], Equals(filter_modaliases(
                self.modaliases, item['modaliases'])))
            # Delete this so we can compare the matches to what was expected.
            del item['matches']
        expected_ruled_out = [
            self.hardware_database[index]
            for index in self.expected_ruled_out_indexes
        ]
        self.assertThat(discovered, Equals(expected_matches))
        self.assertThat(ruled_out, Equals(expected_ruled_out))

    def test__retag_node_for_hardware_by_modalias__precreate_parent(self):
        node = factory.make_Node()
        parent_tag = factory.make_Tag()
        parent_tag_name = parent_tag.name
        # Need to pre-create these so the code can remove them.
        expected_removed = set([
            factory.make_Tag(name=self.hardware_database[index]['tag'])
            for index in self.expected_ruled_out_indexes])
        for tag in expected_removed:
            node.tags.add(tag)
        added, removed = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database)
        expected_added = set([
            Tag.objects.get(name=self.hardware_database[index]['tag'])
            for index in self.expected_match_indexes])
        if len(expected_added) > 0:
            expected_added.add(parent_tag)
        else:
            expected_removed.add(parent_tag)
        self.assertThat(added, Equals(expected_added))
        self.assertThat(removed, Equals(expected_removed))
        # Run again to confirm that we added the same tags.
        added, removed = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database)
        self.assertThat(added, Equals(expected_added))

    def test__retag_node_for_hardware_by_modalias__adds_parent_tag(self):
        node = factory.make_Node()
        parent_tag_name = "parent-tag-name"
        added, _ = retag_node_for_hardware_by_modalias(
            node, self.modaliases, parent_tag_name, self.hardware_database)
        # Test that the parent tag was created if the hardware matched.
        if len(added) > 0:
            self.assertIsNotNone(Tag.objects.get(name=parent_tag_name))


class TestAddSwitchVendorModelTags(MAASServerTestCase):

    def test_sets_wedge40_kernel_opts(self):
        node = factory.make_Node()
        add_switch_vendor_model_tags(node, 'accton', 'wedge40')
        tags = set(node.tags.all().values_list('name', flat=True))
        self.assertThat(tags, Equals({'accton', 'wedge40'}))
        tag = Tag.objects.get(name="wedge40")
        self.assertThat(tag.kernel_opts, Equals(
            "console=tty0 console=ttyS1,57600n8"))

    def test_sets_wedge100_kernel_opts(self):
        node = factory.make_Node()
        add_switch_vendor_model_tags(node, 'accton', 'wedge100')
        tags = set(node.tags.all().values_list('name', flat=True))
        self.assertThat(tags, Equals({'accton', 'wedge100'}))
        tag = Tag.objects.get(name="wedge100")
        self.assertThat(tag.kernel_opts, Equals(
            "console=tty0 console=ttyS4,57600n8"))


class TestCreateMetadataByModalias(MAASServerTestCase):

    scenarios = (
        ('switch_trident2', {
            'modaliases':
                b'pci:xxx\n'
                b'pci:v000014E4d0000B850sv0sd1bc2sc3i4\n'
                b'dmi:svnJoytech:pnWedge-AC-F20-001329\n'
                b'pci:yyy\n',
            'expected_tags': {
                'accton',
                'switch',
                'bcm-trident2-asic',
                'wedge40',
            },
            'expected_driver': '',
            'expected_vendor': 'accton',
            'expected_model': 'wedge40',
        }),
        ('switch_tomahawk', {
            'modaliases':
                b'pci:xxx\n'
                b'pci:v000014E4d0000B960sv0sd1bc2sc3i4\n'
                b"dmi:svnTobefilledbyO.E.M.:pnTobefilledbyO.E.M.:"
                b"rnPCOM-B632VG-ECC-FB-ACCTON-D\n"
                b'pci:yyy\n',
            'expected_tags': {
                'accton',
                'switch',
                'bcm-tomahawk-asic',
                'wedge100',
            },
            'expected_driver': '',
            'expected_vendor': 'accton',
            'expected_model': 'wedge100',
        }),
        ('no_matcj', {
            'modaliases':
                b'pci:xxx\n'
                b'pci:yyy\n',
            'expected_tags': set(),
            'expected_driver': None,
            'expected_vendor': None,
            'expected_model': None,
        }),
    )

    def test__tags_node_appropriately(self):
        node = factory.make_Node()
        create_metadata_by_modalias(node, self.modaliases, 0)
        tags = set(node.tags.all().values_list('name', flat=True))
        self.assertThat(tags, Equals(self.expected_tags))
        if self.expected_driver is not None:
            switch = Switch.objects.get(node=node)
            self.assertThat(switch.nos_driver, Equals(self.expected_driver))
        metadata = node.get_metadata()
        self.assertThat(metadata.get("vendor-name"),
                        Equals(self.expected_vendor))
        self.assertThat(metadata.get("physical-model-name"),
                        Equals(self.expected_model))


class TestAddSwitchModels(MAASServerTestCase):

    def test_sets_switch_driver_to_empty_string(self):
        node = factory.make_Node()
        switch = add_switch(node, 'vendor', 'switch')
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
        self.assertEqual({
            NODE_METADATA.PHYSICAL_MODEL_NAME: "Wedge100ACFO",
            NODE_METADATA.PHYSICAL_SERIAL_NUM: "AH19058615",
            NODE_METADATA.PHYSICAL_HARDWARE_REV: "1",
            NODE_METADATA.PHYSICAL_MFG_NAME: "Accton",
        }, metadata)


class TestUpdateHardwareDetails(MAASServerTestCase):

    doctest_flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE

    def test_hardware_updates_hardware_uuid(self):
        node = factory.make_Node()
        hardware_uuid = factory.make_UUID()
        xmlbytes = dedent("""\
        <node>
            <configuration>
                <setting id="uuid" value="%s" />
            </configuration>
        </node>
        """ % hardware_uuid).encode()
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        self.assertEquals(hardware_uuid, node.hardware_uuid)

    def test_hardware_updates_ignores_empty_tags(self):
        # Tags with empty definitions are ignored when
        # update_hardware_details gets called.
        factory.make_Tag(definition='')
        node = factory.make_Node()
        node.save()
        xmlbytes = '<node/>'.encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        # The real test is that update_hardware_details does not blow
        # up, see bug 1131418.
        self.assertEqual([], list(node.tags.all()))

    def test_hardware_updates_logs_invalid_xml(self):
        logger = self.useFixture(FakeLogger())
        update_hardware_details(factory.make_Node(), b"garbage", 0)
        expected_log = dedent("""\
        Invalid lshw data.
        Traceback (most recent call last):
        ...
        lxml.etree.XMLSyntaxError: Start tag expected, ...
        """)
        self.assertThat(
            logger.output, DocTestMatches(
                expected_log, self.doctest_flags))

    def test_hardware_updates_does_nothing_when_exit_status_is_not_zero(self):
        logger = self.useFixture(FakeLogger(name='commissioningscript'))
        update_hardware_details(factory.make_Node(), b"garbage", exit_status=1)
        self.assertEqual("", logger.output)

    def test_hardware_updates_node_attribs(self):
        node = factory.make_Node()
        system_vendor = factory.make_name('system_vendor')
        system_product = factory.make_name('system_product')
        system_version = factory.make_name('system_version')
        system_serial = factory.make_name('system_serial')
        mainboard_vendor = factory.make_name('mainboard_vendor')
        mainboard_product = factory.make_name('mainboard_product')
        mainboard_firmware_version = factory.make_name(
            'mainboard_firmware_version')
        mainboard_firmware_date = factory.make_name(
            'mainboard_firmware_date')
        xmlbytes = dedent("""\
        <node>
          <node class="system">
            <vendor>%s</vendor>
            <product>%s</product>
            <version>%s</version>
            <serial>%s</serial>
          </node>
          <node id="core">
            <vendor>%s</vendor>
            <product>%s</product>
            <node id="firmware">
              <version>%s</version>
              <date>%s</date>
            </node>
          </node>
        </node>
        """ % (
            system_vendor, system_product, system_version, system_serial,
            mainboard_vendor, mainboard_product, mainboard_firmware_version,
            mainboard_firmware_date)).encode()
        update_hardware_details(node, xmlbytes, 0)

        nmd = NodeMetadata.objects.get(node=node, key='system_vendor')
        self.assertEquals(system_vendor, nmd.value)
        nmd = NodeMetadata.objects.get(node=node, key='system_product')
        self.assertEquals(system_product, nmd.value)
        nmd = NodeMetadata.objects.get(node=node, key='system_version')
        self.assertEquals(system_version, nmd.value)
        nmd = NodeMetadata.objects.get(node=node, key='system_serial')
        self.assertEquals(system_serial, nmd.value)

        nmd = NodeMetadata.objects.get(node=node, key='mainboard_vendor')
        self.assertEquals(mainboard_vendor, nmd.value)
        nmd = NodeMetadata.objects.get(node=node, key='mainboard_product')
        self.assertEquals(mainboard_product, nmd.value)
        nmd = NodeMetadata.objects.get(
            node=node, key='mainboard_firmware_version')
        self.assertEquals(mainboard_firmware_version, nmd.value)
        nmd = NodeMetadata.objects.get(
            node=node, key='mainboard_firmware_date')
        self.assertEquals(mainboard_firmware_date, nmd.value)

    def test_hardware_ignores_empty_or_missing_node_attribs(self):
        node = factory.make_Node()
        xmlbytes = dedent("""\
        <node>
          <node class="system">
            <vendor></vendor>
            <product>0123456789</product>
          </node>
        </node>
        """).encode()
        update_hardware_details(node, xmlbytes, 0)

        for key in [
                'system_vendor', 'system_product', 'system_version',
                'system_serial', 'mainboard_Vendor', 'mainboard_product',
                'mainboard_firmware_version', 'mainboard_firmware_date']:
            self.assertIsNone(NodeMetadata.objects.get(node=node, key=key))


class TestProcessLXDResults(MAASServerTestCase):

    def test__updates_memory(self):
        node = factory.make_Node()
        node.memory = random.randint(4096, 8192)
        node.save()
        self.patch(hooks_module, 'update_node_network_information')

        process_lxd_results(
            node, json.dumps(SAMPLE_LXD_JSON).encode('utf-8'), 0)
        node = reload_object(node)
        self.assertEqual(round(16691519488 / 1024 / 1024), node.memory)

    def test__updates_model_and_cpu_speed_from_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(hooks_module, 'update_node_network_information')

        process_lxd_results(
            node, json.dumps(SAMPLE_LXD_JSON).encode('utf-8'), 0)
        node = reload_object(node)
        self.assertEqual(2400, node.cpu_speed)
        nmd = NodeMetadata.objects.get(node=node, key='cpu_model')
        self.assertEqual('Intel(R) Core(TM) i7-4700MQ CPU', nmd.value)

    def test__updates_cpu_speed_with_max_frequency_when_not_in_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(hooks_module, 'update_node_network_information')

        NO_SPEED_IN_NAME = deepcopy(SAMPLE_LXD_JSON)
        NO_SPEED_IN_NAME['cpu']['sockets'][0]['name'] = (
            'Intel(R) Core(TM) i7-4700MQ CPU')
        process_lxd_results(
            node, json.dumps(NO_SPEED_IN_NAME).encode('utf-8'), 0)
        node = reload_object(node)
        self.assertEqual(3400, node.cpu_speed)

    def test__updates_cpu_speed_with_current_frequency_when_not_in_name(self):
        node = factory.make_Node()
        node.cpu_speed = 9999
        node.save()
        self.patch(hooks_module, 'update_node_network_information')

        NO_NAME_OR_MAX_FREQ = deepcopy(SAMPLE_LXD_JSON)
        del NO_NAME_OR_MAX_FREQ['cpu']['sockets'][0]['name']
        del NO_NAME_OR_MAX_FREQ['cpu']['sockets'][0]['frequency_turbo']
        process_lxd_results(
            node, json.dumps(NO_NAME_OR_MAX_FREQ).encode('utf-8'), 0)
        node = reload_object(node)
        self.assertEqual(3200, node.cpu_speed)


class TestUpdateNodePhysicalBlockDevices(MAASServerTestCase):

    def make_block_device(
            self, name=None, path=None, id_path=None, size=None,
            block_size=None, model=None, serial=None, rotary=True, rpm=None,
            removable=False, sata=False, firmware_version=None):
        if name is None:
            name = factory.make_name('name')
        if path is None:
            path = '/dev/%s' % name
        if id_path is None:
            id_path = '/dev/disk/by-id/deviceid'
        if size is None:
            size = random.randint(
                MIN_BLOCK_DEVICE_SIZE * 10, MIN_BLOCK_DEVICE_SIZE * 100)
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if model is None:
            model = factory.make_name('model')
        if serial is None:
            serial = factory.make_name('serial')
        if rpm is None:
            rpm = random.choice(('4800', '5400', '10000', '15000'))
        if firmware_version is None:
            firmware_version = factory.make_name('firmware_version')
        return {
            "NAME": name,
            "PATH": path,
            "ID_PATH": id_path,
            "SIZE": '%s' % size,
            "BLOCK_SIZE": '%s' % block_size,
            "MODEL": model,
            "SERIAL": serial,
            "RO": "0",
            "RM": "1" if removable else "0",
            "ROTA": "1" if rotary else "0",
            "SATA": "1" if sata else "0",
            "RPM": "0" if not rotary else rpm,
            "FIRMWARE_VERSION": firmware_version,
            }

    def test__idempotent_block_devices(self):
        devices = [self.make_block_device() for _ in range(3)]
        device_names = [device['NAME'] for device in devices]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        update_node_physical_block_devices(node, json_output, 0)
        devices = list(PhysicalBlockDevice.objects.filter(node=node))
        created_names = []
        for device in devices:
            created_names.append(device.name)
            self.assertEqual(device.numa_node, node.default_numanode)
        self.assertItemsEqual(device_names, created_names)

    def test__does_nothing_when_exit_status_is_not_zero(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, b"garbage", exit_status=1)
        self.assertIsNotNone(reload_object(block_device))

    def test__does_nothing_if_skip_storage(self):
        node = factory.make_Node(skip_storage=True)
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, b"garbage", exit_status=0)
        self.assertIsNotNone(reload_object(block_device))
        self.assertFalse(reload_object(node).skip_storage)

    def test__removes_previous_physical_block_devices(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, b"[]", 0)
        self.assertIsNone(reload_object(block_device))

    def test__creates_physical_block_devices(self):
        devices = [self.make_block_device() for _ in range(3)]
        device_names = [device['NAME'] for device in devices]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        created_names = [
            device.name
            for device in PhysicalBlockDevice.objects.filter(node=node)
            ]
        self.assertItemsEqual(device_names, created_names)

    def test__handles_renamed_block_device(self):
        devices = [self.make_block_device(name='sda', serial='first')]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        devices = [
            self.make_block_device(name='sda', serial='second'),
            self.make_block_device(name='sdb', serial='first'),
        ]
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        device_names = [device['NAME'] for device in devices]
        created_names = [
            device.name
            for device in PhysicalBlockDevice.objects.filter(node=node)
            ]
        self.assertItemsEqual(device_names, created_names)

    def test__handles_new_block_device_in_front(self):
        # First simulate a node being commissioned with two disks. For
        # this test, there need to be at least two disks in order to
        # simulate a condition like the one in bug #1662343.
        node = factory.make_Node()
        device1 = self.make_block_device(name='sda')
        device2 = self.make_block_device(name='sdb')
        update_node_physical_block_devices(
            node, json.dumps([device1, device2]).encode('utf-8'), 0)

        # Now, we simulate that we insert a new disk in the machine that
        # becomes sda, thus pushing the other disks to sdb and sdc.
        recommission_device1 = self.make_block_device(name='sda')
        recommission_device2 = device1.copy()
        recommission_device2["NAME"] = 'sdb'
        recommission_device2["PATH"] = '/dev/sdb'
        recommission_device3 = device2.copy()
        recommission_device3["NAME"] = 'sdc'
        recommission_device3["PATH"] = '/dev/sdc'
        recommission_devices = [
            recommission_device1, recommission_device2, recommission_device3]

        # After recommissioning the node, we'll have three devices, as
        # expected.
        update_node_physical_block_devices(
            node, json.dumps(recommission_devices).encode('utf-8'), 0)
        device_names = [
            (device.name, device.serial)
            for device in PhysicalBlockDevice.objects.filter(node=node)
            ]
        self.assertItemsEqual(
            [('sda', recommission_device1["SERIAL"]),
             ('sdb', recommission_device2["SERIAL"]),
             ('sdc', recommission_device3["SERIAL"])],
            device_names)

    def test__only_updates_physical_block_devices(self):
        devices = [self.make_block_device() for _ in range(3)]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        created_ids_one = [
            device.id
            for device in PhysicalBlockDevice.objects.filter(node=node)
            ]
        update_node_physical_block_devices(node, json_output, 0)
        created_ids_two = [
            device.id
            for device in PhysicalBlockDevice.objects.filter(node=node)
            ]
        self.assertItemsEqual(created_ids_two, created_ids_one)

    def test__doesnt_reset_boot_disk(self):
        devices = [self.make_block_device() for _ in range(3)]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        boot_disk = PhysicalBlockDevice.objects.filter(node=node).first()
        node.boot_disk = boot_disk
        node.save()
        update_node_physical_block_devices(node, json_output, 0)
        self.assertEqual(boot_disk, reload_object(node).boot_disk)

    def test__clears_boot_disk(self):
        devices = [self.make_block_device() for _ in range(3)]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        update_node_physical_block_devices(
            node, json.dumps([]).encode('utf-8'), 0)
        self.assertIsNone(reload_object(node).boot_disk)

    def test__creates_physical_block_devices_in_order(self):
        devices = [self.make_block_device() for _ in range(3)]
        device_names = [device['NAME'] for device in devices]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        created_names = [
            device.name
            for device in (
                PhysicalBlockDevice.objects.filter(node=node).order_by('id'))
            ]
        self.assertEqual(device_names, created_names)

    def test__creates_physical_block_device(self):
        name = factory.make_name('name')
        id_path = '/dev/disk/by-id/deviceid'
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        firmware_version = factory.make_name('firmware_version')
        device = self.make_block_device(
            name=name, size=size, block_size=block_size,
            model=model, serial=serial, firmware_version=firmware_version)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
            MatchesStructure.byEquality(
                name=name, id_path=id_path, size=size,
                block_size=block_size, model=model, serial=serial,
                firmware_version=firmware_version))

    def test__creates_physical_block_device_with_path(self):
        name = factory.make_name('name')
        size = random.randint(MIN_BLOCK_DEVICE_SIZE, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        firmware_version = factory.make_name('firmware_version')
        device = self.make_block_device(
            name=name, size=size, block_size=block_size,
            model=model, serial=serial, id_path='',
            firmware_version=firmware_version)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
            MatchesStructure.byEquality(
                name=name, id_path='/dev/%s' % name, size=size,
                block_size=block_size, model=model, serial=serial,
                firmware_version=firmware_version))

    def test__creates_physical_block_device_with_path_for_missing_serial(self):
        name = factory.make_name('name')
        size = random.randint(MIN_BLOCK_DEVICE_SIZE + 1, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        model = factory.make_name('model')
        serial = ''
        device = self.make_block_device(
            name=name, size=size, block_size=block_size,
            model=model, serial=serial, id_path='bogus')
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
            MatchesStructure.byEquality(
                name=name, id_path='/dev/%s' % name, size=size,
                block_size=block_size, model=model, serial=serial))

    def test__creates_physical_block_device_only_for_node(self):
        device = self.make_block_device()
        node = factory.make_Node(with_boot_disk=False)
        other_node = factory.make_Node(with_boot_disk=False)
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertEqual(
            0, PhysicalBlockDevice.objects.filter(node=other_node).count(),
            "Created physical block device for the incorrect node.")

    def test__creates_physical_block_device_with_rotary_tag(self):
        device = self.make_block_device(rotary=True)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('rotary'))
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('ssd')))

    def test__creates_physical_block_device_with_rotary_and_rpm_tags(self):
        device = self.make_block_device(rotary=True, rpm=5400)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('rotary'))
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('5400rpm'))

    def test__creates_physical_block_device_with_ssd_tag(self):
        device = self.make_block_device(rotary=False)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            ContainsAll(['ssd']))
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('rotary')))

    def test__creates_physical_block_device_without_removable_tag(self):
        device = self.make_block_device(removable=False)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('removable')))

    def test__creates_physical_block_device_with_removable_tag(self):
        device = self.make_block_device(removable=True)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('removable'))

    def test__creates_physical_block_device_without_sata_tag(self):
        device = self.make_block_device(sata=False)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('sata')))

    def test__creates_physical_block_device_with_sata_tag(self):
        device = self.make_block_device(sata=True)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('sata'))

    def test__ignores_min_block_device_size_devices(self):
        device = self.make_block_device(
            size=random.randint(1, MIN_BLOCK_DEVICE_SIZE))
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertEquals(
            0, len(PhysicalBlockDevice.objects.filter(node=node)))

    def test__ignores_loop_devices(self):
        device = self.make_block_device(id_path='/dev/loop0')
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertEquals(
            0, len(PhysicalBlockDevice.objects.filter(node=node)))

    def test__regenerates_testing_script_set(self):
        device = self.make_block_device()
        node = factory.make_Node()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={'storage': {'type': 'storage'}})
        node.current_testing_script_set = (
            ScriptSet.objects.create_testing_script_set(
                node=node, scripts=[script.name]))
        node.save()

        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)

        self.assertEquals(1, len(node.get_latest_testing_script_results))
        script_result = node.get_latest_testing_script_results.get(
            script=script)
        self.assertDictEqual({'storage': {
            'type': 'storage',
            'value': {
                'id_path': device['ID_PATH'],
                'physical_blockdevice_id': (
                    node.physicalblockdevice_set.first().id),
                'name': device['NAME'],
                'serial': device['SERIAL'],
                'model': device['MODEL'],
            }}}, script_result.parameters)

    def test__sets_default_configuration(self):
        device = self.make_block_device()
        node = factory.make_Node()

        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)

        _, layout = get_applied_storage_layout_for_node(node)
        self.assertEquals(
            Config.objects.get_config('default_storage_layout'), layout)


class TestUpdateNodeNetworkInterfaceTags(MAASServerTestCase):
    """Test the update_node_network_interface_tags function using data from
    """

    SRIOV_OUTPUT = dedent("""\
        eth0 00:00:00:00:00:01
        eth1 00:00:00:00:00:02
        """).encode("utf-8")

    def test_set_sriov_interface_tag(self):
        """Test the update_node_network_interface_tags creates 'sriov' tag
        for network interfaces in the commissioning output. (SRIOV_OUTPUT)
        """
        node = factory.make_Node()

        # Create network interfaces to add the tags to.
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, name="eth0",
                               mac_address="00:00:00:00:00:01", node=node)
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, name="eth1",
                               mac_address="00:00:00:00:00:02", node=node)
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, name="eth2",
                               mac_address="00:00:00:00:00:03", node=node)

        update_node_network_interface_tags(node, self.SRIOV_OUTPUT, 0)

        # Test that interfaces in SRIOV_OUTPUT have tag
        self.assertThat(Interface.objects.filter(node=node,
                        mac_address="00:00:00:00:00:01").first().tags,
                        Contains('sriov'))
        self.assertThat(Interface.objects.filter(node=node,
                        mac_address="00:00:00:00:00:02").first().tags,
                        Contains('sriov'))
        # Test that interfaces not in SRIOV_OUTPUT do not have the tag
        self.assertNotIn('sriov', Interface.objects.filter(node=node,
                         mac_address="00:00:00:00:00:03").first().tags)


class TestUpdateNodeNetworkInformation(MAASServerTestCase):
    """Tests the update_node_network_information function using data from LXD.

    The EXPECTED_MACS dictionary below must match the contents of the file,
    which should specify a list of physical interfaces (such as what would
    be expected to be found during commissioning).
    """
    EXPECTED_INTERFACES = {
        'eth0': MAC("00:00:00:00:00:01"),
        'eth1': MAC("00:00:00:00:00:02"),
        'eth2': MAC("00:00:00:00:00:03"),
    }

    EXPECTED_INTERFACES_XENIAL = {
        'ens3': MAC("52:54:00:2d:39:49"),
        'ens10': MAC("52:54:00:e5:c6:6b"),
        'ens11': MAC("52:54:00:ed:9f:9d"),
        'ens12': MAC("52:54:00:ed:9f:00"),
    }

    IP_ADDR_OUTPUT_FILE = os.path.join(
        os.path.dirname(__file__), 'ip_addr_results.txt')
    with open(IP_ADDR_OUTPUT_FILE, "rb") as fd:
        IP_ADDR_OUTPUT = fd.read()
    IP_ADDR_OUTPUT_FILE = os.path.join(
        os.path.dirname(__file__), 'ip_addr_results_xenial.txt')
    with open(IP_ADDR_OUTPUT_FILE, "rb") as fd:
        IP_ADDR_OUTPUT_XENIAL = fd.read()
    IP_ADDR_WEDGE_OUTPUT_FILE = os.path.join(
        os.path.dirname(__file__), 'ip_addr_results_wedge100.txt')
    with open(IP_ADDR_WEDGE_OUTPUT_FILE, "rb") as fd:
        IP_ADDR_WEDGE_OUTPUT = fd.read()

    def create_IPADDR_OUTPUT_NAME_script(self, node, output):
        script = factory.make_Script(
            name=IPADDR_OUTPUT_NAME, script_type=SCRIPT_TYPE.COMMISSIONING)
        commissioning_script_set = (
            ScriptSet.objects.create_commissioning_script_set(
                node, scripts=[script.name]))
        node.current_commissioning_script_set = commissioning_script_set
        factory.make_ScriptResult(
            script_set=commissioning_script_set, script=script,
            exit_status=0, status=SCRIPT_STATUS.PASSED, output=output)

    def assert_expected_interfaces_and_macs_exist_for_node(
            self, node, expected_interfaces=EXPECTED_INTERFACES):
        """Asserts to ensure that the type, name, and MAC address are
        appropriate, given Node's interfaces. (and an optional list of
        expected interfaces which must exist)
        """
        node_interfaces = list(Interface.objects.filter(node=node))

        expected_interfaces = expected_interfaces.copy()

        self.assertThat(len(node_interfaces), Equals(len(expected_interfaces)))

        for interface in node_interfaces:
            if (interface.name.startswith('eth') or
                    interface.name.startswith('ens')):
                parts = interface.name.split('.')
                if len(parts) == 2 and parts[1].isdigit():
                    iftype = INTERFACE_TYPE.VLAN
                else:
                    iftype = INTERFACE_TYPE.PHYSICAL
                self.assertThat(
                    interface.type, Equals(iftype))
            self.assertIn(interface.name, expected_interfaces)
            self.assertThat(interface.mac_address, Equals(
                expected_interfaces[interface.name]))
            self.assertEqual(interface.numa_node, node.default_numanode)

    def test__does_nothing_if_skip_networking(self):
        node = factory.make_Node(interface=True, skip_networking=True)
        boot_interface = node.get_boot_interface()
        update_node_network_information(node, SAMPLE_LXD_JSON)
        self.assertIsNotNone(reload_object(boot_interface))
        self.assertFalse(reload_object(node).skip_networking)

    def test__add_all_interfaces(self):
        """Test a node that has no previously known interfaces on which we
        need to add a series of interfaces.
        """
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        update_node_network_information(node, SAMPLE_LXD_JSON)

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test__add_all_interfaces_xenial(self):
        """Test a node that has no previously known interfaces on which we
        need to add a series of interfaces.
        """
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT_XENIAL)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_JSON)
        XENIAL_NETWORK['network'] = SAMPLE_LXD_XENIAL_NETWORK_JSON
        update_node_network_information(node, XENIAL_NETWORK)

        # Makes sure all the test dataset MAC addresses were added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(
            node, expected_interfaces=self.EXPECTED_INTERFACES_XENIAL)

    def test__adds_lshw_info(self):
        """Test a node that has no previously known interfaces gets info from
        lshw added.
        """
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        vendor = factory.make_name('vendor')
        product = factory.make_name('product')
        firmware_version = factory.make_name('firmware_version')
        lshw = node.current_commissioning_script_set.find_script_result(
            script_name=LSHW_OUTPUT_NAME)
        lshw_xml = dedent("""\
        <node class="network">
            <serial>00:00:00:00:00:01</serial>
            <vendor>%s</vendor>
            <product>%s</product>
            <configuration>
                <setting id="firmware" value="%s" />
            </configuration>
        </node>
        """ % (vendor, product, firmware_version)).encode()
        lshw.store_result(0, stdout=lshw_xml)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        nic = Interface.objects.get(mac_address='00:00:00:00:00:01')
        self.assertEqual(vendor, nic.vendor)
        self.assertEqual(product, nic.product)
        self.assertEqual(firmware_version, nic.firmware_version)

    def test__ignores_bad_lshw(self):
        """Test a node that has no previous known interfaces ignores bad lshw
        data.
        """
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        lshw = node.current_commissioning_script_set.find_script_result(
            script_name=LSHW_OUTPUT_NAME)
        lshw.store_result(0, stdout=factory.make_string().encode())

        update_node_network_information(node, SAMPLE_LXD_JSON)

        nic = Interface.objects.get(mac_address='00:00:00:00:00:01')
        self.assertIsNone(nic.vendor)
        self.assertIsNone(nic.product)
        self.assertIsNone(nic.firmware_version)

    def test__ignores_empty_or_missing_lshw_data(self):
        """Test a node that has no previously known interfaces gets info from
        lshw added.
        """
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        lshw = node.current_commissioning_script_set.find_script_result(
            script_name=LSHW_OUTPUT_NAME)
        lshw_xml = dedent("""\
        <node class="network">
            <serial>00:00:00:00:00:01</serial>
            <vendor></vendor>
            <configuration>
                <setting id="firmware" />
            </configuration>
        </node>
        """).encode()
        lshw.store_result(0, stdout=lshw_xml)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        nic = Interface.objects.get(mac_address='00:00:00:00:00:01')
        self.assertIsNone(nic.vendor)
        self.assertIsNone(nic.product)
        self.assertIsNone(nic.firmware_version)

    def test__one_mac_missing(self):
        """Test whether we correctly detach a NIC that no longer appears to be
        connected to the node.
        """
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        # Create a MAC address that we know is not in the test dataset.
        factory.make_Interface(
            node=node, mac_address="01:23:45:67:89:ab")

        update_node_network_information(node, SAMPLE_LXD_JSON)

        # These should have been added to the node.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

        # This one should have been removed because it no longer shows on the
        # `ip addr` output.
        db_macaddresses = [
            iface.mac_address for iface in node.interface_set.all()
            ]
        self.assertNotIn(MAC('01:23:45:67:89:ab'), db_macaddresses)

    def test__reassign_mac(self):
        """Test whether we can assign a MAC address previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()

        # Create a MAC address that we know IS in the test dataset.
        interface_to_be_reassigned = factory.make_Interface(node=node1)
        interface_to_be_reassigned.mac_address = MAC('00:00:00:00:00:01')
        interface_to_be_reassigned.save()

        node2 = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node2, self.IP_ADDR_OUTPUT)
        update_node_network_information(node2, SAMPLE_LXD_JSON)

        self.assert_expected_interfaces_and_macs_exist_for_node(node2)

        # Ensure the MAC object moved over to node2.
        self.assertItemsEqual([], Interface.objects.filter(node=node1))
        self.assertItemsEqual([], Interface.objects.filter(node=node1))

    def test__reassign_interfaces(self):
        """Test whether we can assign interfaces previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()
        script = factory.make_Script(
            name=IPADDR_OUTPUT_NAME, script_type=SCRIPT_TYPE.COMMISSIONING)
        commissioning_script_set_node1 = (
            ScriptSet.objects.create_commissioning_script_set(
                node1, scripts=[script.name]))
        node1.current_commissioning_script_set = commissioning_script_set_node1
        factory.make_ScriptResult(
            script_set=commissioning_script_set_node1,
            script=script, exit_status=0, status=SCRIPT_STATUS.PASSED,
            output=self.IP_ADDR_OUTPUT)
        update_node_network_information(node1, SAMPLE_LXD_JSON)

        # First make sure the first node has all the expected interfaces.
        self.assert_expected_interfaces_and_macs_exist_for_node(node1)

        # Grab the id from one of the created interfaces.
        interface_id = Interface.objects.filter(node=node1).first().id

        # Now make sure the second node has them all.
        node2 = factory.make_Node()
        commissioning_script_set_node2 = (
            ScriptSet.objects.create_commissioning_script_set(
                node2, scripts=[script.name]))
        node2.current_commissioning_script_set = commissioning_script_set_node2
        factory.make_ScriptResult(
            script_set=commissioning_script_set_node2,
            script=script, exit_status=0, status=SCRIPT_STATUS.PASSED,
            output=self.IP_ADDR_OUTPUT)
        update_node_network_information(node2, SAMPLE_LXD_JSON)

        self.assert_expected_interfaces_and_macs_exist_for_node(node2)

        # Now make sure all the objects moved to the second node.
        self.assertItemsEqual([], Interface.objects.filter(node=node1))
        self.assertItemsEqual([], Interface.objects.filter(node=node1))

        # ... and ensure that the interface was deleted.
        self.assertItemsEqual([], Interface.objects.filter(id=interface_id))

    def test__deletes_virtual_interfaces_with_shared_mac(self):
        # Note: since this VLANInterface will be linked to the default VLAN
        # ("vid 0", which is actually invalid) the VLANInterface will
        # automatically get the name "vlan0".
        ETH0_MAC = self.EXPECTED_INTERFACES['eth0'].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES['eth1'].get_raw()
        BOND_NAME = 'bond0'
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        eth0 = factory.make_Interface(
            name="eth0", mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(
            name="eth1", mac_address=ETH1_MAC, node=node)

        factory.make_Interface(
            INTERFACE_TYPE.VLAN, mac_address=ETH0_MAC, parents=[eth0],
            node=node)
        factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=ETH1_MAC, parents=[eth1],
            node=node, name=BOND_NAME)

        update_node_network_information(node, SAMPLE_LXD_JSON)
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test__interface_names_changed(self):
        # Note: the MACs here are swapped compared to their expected values.
        ETH0_MAC = self.EXPECTED_INTERFACES['eth1'].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES['eth0'].get_raw()
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name="eth0", mac_address=ETH0_MAC,
            node=node)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name="eth1", mac_address=ETH1_MAC,
            node=node)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        # This will ensure that the interfaces were renamed appropriately.
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test__mac_id_is_preserved(self):
        """Test whether MAC address entities are preserved and not recreated"""
        ETH0_MAC = self.EXPECTED_INTERFACES['eth0'].get_raw()
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        iface_to_be_preserved = factory.make_Interface(
            mac_address=ETH0_MAC, node=node)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        self.assertIsNotNone(reload_object(iface_to_be_preserved))

    def test__legacy_model_upgrade_preserves_interfaces(self):
        ETH0_MAC = self.EXPECTED_INTERFACES['eth0'].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES['eth1'].get_raw()
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(mac_address=ETH1_MAC, node=node)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        self.assertEqual(eth0, Interface.objects.get(id=eth0.id))
        self.assertEqual(eth1, Interface.objects.get(id=eth1.id))

        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test__legacy_model_with_extra_mac(self):
        ETH0_MAC = self.EXPECTED_INTERFACES['eth0'].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES['eth1'].get_raw()
        ETH2_MAC = self.EXPECTED_INTERFACES['eth2'].get_raw()
        ETH3_MAC = '00:00:00:00:01:04'
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(mac_address=ETH1_MAC, node=node)
        eth2 = factory.make_Interface(mac_address=ETH2_MAC, node=node)
        eth3 = factory.make_Interface(mac_address=ETH3_MAC, node=node)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        self.assert_expected_interfaces_and_macs_exist_for_node(node)

        # Make sure we re-used the existing MACs in the database.
        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNotNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(eth2))

        # Make sure the interface that no longer exists has been removed.
        self.assertIsNone(reload_object(eth3))

    def test__deletes_virtual_interfaces_with_unique_mac(self):
        ETH0_MAC = self.EXPECTED_INTERFACES['eth0'].get_raw()
        ETH1_MAC = self.EXPECTED_INTERFACES['eth1'].get_raw()
        BOND_MAC = '00:00:00:00:01:02'
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(mac_address=ETH0_MAC, node=node)
        eth1 = factory.make_Interface(mac_address=ETH1_MAC, node=node)
        factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[eth0])
        factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=BOND_MAC, node=node,
            parents=[eth1])

        update_node_network_information(node, SAMPLE_LXD_JSON)
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test__deletes_virtual_interfaces_linked_to_removed_macs(self):
        VLAN_MAC = '00:00:00:00:01:01'
        BOND_MAC = '00:00:00:00:01:02'
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        eth0 = factory.make_Interface(
            name='eth0', mac_address=VLAN_MAC, node=node)
        eth1 = factory.make_Interface(
            name='eth1', mac_address=BOND_MAC, node=node)
        factory.make_Interface(
            INTERFACE_TYPE.VLAN, mac_address=VLAN_MAC, parents=[eth0])
        factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=BOND_MAC, parents=[eth1])

        update_node_network_information(node, SAMPLE_LXD_JSON)
        self.assert_expected_interfaces_and_macs_exist_for_node(node)

    def test__creates_discovered_ip_address(self):
        node = factory.make_Node()
        cidr = '192.168.0.3/24'
        subnet = factory.make_Subnet(
            cidr=cidr, vlan=VLAN.objects.get_default_vlan())
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        update_node_network_information(node, SAMPLE_LXD_JSON)
        eth0 = Interface.objects.get(node=node, name='eth0')
        address = str(IPNetwork(cidr).ip)
        ipv4_ip = eth0.ip_addresses.get(ip=address)
        self.assertThat(
            ipv4_ip,
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet,
                ip=address))

    def test__creates_discovered_ip_address_on_xenial(self):
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT_XENIAL)
        cidr = '172.16.100.108/24'
        subnet = factory.make_Subnet(
            cidr=cidr, vlan=VLAN.objects.get_default_vlan())
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_JSON)
        XENIAL_NETWORK['network'] = SAMPLE_LXD_XENIAL_NETWORK_JSON
        update_node_network_information(node, XENIAL_NETWORK)
        ens3 = Interface.objects.get(node=node, name='ens3')
        address = str(IPNetwork(cidr).ip)
        ipv4_ip = ens3.ip_addresses.get(ip=address)
        self.assertThat(
            ipv4_ip,
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet,
                ip=address))
        # First IP is DISCOVERED second is AUTO configured.
        self.assertThat(ens3.ip_addresses.count(), Equals(2))

    def test__handles_disconnected_interfaces(self):
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT_XENIAL)
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_JSON)
        XENIAL_NETWORK['network'] = SAMPLE_LXD_XENIAL_NETWORK_JSON
        update_node_network_information(node, XENIAL_NETWORK)
        ens12 = Interface.objects.get(node=node, name='ens12')
        self.assertThat(ens12.vlan, Is(None))

    def test__disconnects_previously_connected_interface(self):
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT_XENIAL)
        subnet = factory.make_Subnet()
        ens12 = factory.make_Interface(
            name='ens12', node=node, mac_address='52:54:00:ed:9f:00',
            subnet=subnet)
        self.assertThat(ens12.vlan, Equals(subnet.vlan))
        XENIAL_NETWORK = deepcopy(SAMPLE_LXD_JSON)
        XENIAL_NETWORK['network'] = SAMPLE_LXD_XENIAL_NETWORK_JSON
        update_node_network_information(node, XENIAL_NETWORK)
        ens12 = Interface.objects.get(node=node, name='ens12')
        self.assertThat(ens12.vlan, Is(None))

    def test__ignores_openbmc_interface(self):
        """Ensure that OpenBMC interface is ignored."""
        node = factory.make_Node()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()

        SWITCH_OPENBMC_MAC_JSON = deepcopy(SAMPLE_LXD_JSON)
        SWITCH_OPENBMC_MAC_JSON[
            'network']['cards'][0]['ports'][0]['address'] = (
                SWITCH_OPENBMC_MAC)

        update_node_network_information(node, SWITCH_OPENBMC_MAC_JSON)

        # Specifically, there is no OpenBMC interface with a fixed MAC address.
        node_interfaces = Interface.objects.filter(node=node)
        all_macs = [interface.mac_address for interface in node_interfaces]
        self.assertNotIn(SWITCH_OPENBMC_MAC, all_macs)

    def test__sets_boot_interface(self):
        """Test a node will have its boot_interface set if none are defined."""
        subnet = factory.make_Subnet(cidr='192.168.0.3/24')
        node = factory.make_Node()

        # Delete all Interfaces created by factory attached to this node.
        Interface.objects.filter(node_id=node.id).delete()
        node.boot_interface = None
        node.boot_cluster_ip = '192.168.0.1'
        node.save()
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        update_node_network_information(node, SAMPLE_LXD_JSON)
        node = reload_object(node)

        self.assertIsNotNone(
            node.boot_interface.vlan.subnet_set.filter(id=subnet.id).first())

    def test__regenerates_testing_script_set(self):
        factory.make_Subnet(cidr='192.168.0.3/24')
        node = factory.make_Node(boot_cluster_ip='192.168.0.1')
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={'interface': {'type': 'interface'}})
        node.current_testing_script_set = (
            ScriptSet.objects.create_testing_script_set(
                node=node, scripts=[script.name]))
        node.save()

        update_node_network_information(node, SAMPLE_LXD_JSON)

        self.assertEquals(1, len(node.get_latest_testing_script_results))
        # The default network layout only configures the boot interface.
        script_result = node.get_latest_testing_script_results.get(
            script=script)
        self.assertDictEqual({'interface': {
            'type': 'interface',
            'value': {
                'name': node.boot_interface.name,
                'mac_address': str(node.boot_interface.mac_address),
                'vendor': node.boot_interface.vendor,
                'product': node.boot_interface.product,
                'interface_id': node.boot_interface.id,
            }}}, script_result.parameters)

    def test__sets_default_configuration(self):
        factory.make_Subnet(cidr='192.168.0.3/24')
        node = factory.make_Node(boot_cluster_ip='192.168.0.1')
        self.create_IPADDR_OUTPUT_NAME_script(node, self.IP_ADDR_OUTPUT)

        update_node_network_information(node, SAMPLE_LXD_JSON)

        # 2 devices configured, one for IPv4 one for IPv6.
        self.assertEquals(2, node.interface_set.filter(
            ip_addresses__alloc_type=IPADDRESS_TYPE.AUTO).count())
