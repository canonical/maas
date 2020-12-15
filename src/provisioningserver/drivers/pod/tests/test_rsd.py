# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod.rsd`."""


from copy import deepcopy
from http import HTTPStatus
from io import BytesIO
import json
from os.path import join
import random
from unittest.mock import call

from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import FileBodyProducer, PartialDownloadError
from twisted.web.http_headers import Headers

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.pod import (
    BlockDeviceType,
    Capabilities,
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    PodActionError,
    PodFatalError,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
import provisioningserver.drivers.pod.rsd as rsd_module
from provisioningserver.drivers.pod.rsd import (
    RSD_NODE_POWER_STATE,
    RSD_SYSTEM_POWER_STATE,
    RSDPodDriver,
)
from provisioningserver.rpc.exceptions import PodInvalidResources

SAMPLE_JSON_PARTIAL_DOWNLOAD_ERROR = {
    "error": {
        "code": "Base.1.0.ResourcesStateMismatch",
        "message": "Conflict during allocation",
        "@Message.ExtendedInfo": [
            {
                "Message": "There are no computer systems available for"
                " this allocation request."
            },
            {
                "Message": "Available assets count after applying "
                + "filters: [available: 9 -> status: 9 -> resource: "
                + "9 -> chassis: 9 -> processors: 0 -> memory: 0 -> "
                + "local drives: 0 -> ethernet interfaces: 0]"
            },
        ],
    }
}


SAMPLE_JSON_SYSTEMS = {
    "@odata.context": "/redfish/v1/$metadata#Systems",
    "@odata.id": "/redfish/v1/Systems",
    "@odata.type": "#ComputerSystemCollection.ComputerSystemCollection",
    "Name": "Computer System Collection",
    "Description": "Computer System Collection",
    "Members@odata.count": 8,
    "Members": [
        {"@odata.id": "/redfish/v1/Systems/1"},
        {"@odata.id": "/redfish/v1/Systems/2"},
        {"@odata.id": "/redfish/v1/Systems/3"},
        {"@odata.id": "/redfish/v1/Systems/4"},
        {"@odata.id": "/redfish/v1/Systems/5"},
        {"@odata.id": "/redfish/v1/Systems/6"},
        {"@odata.id": "/redfish/v1/Systems/7"},
        {"@odata.id": "/redfish/v1/Systems/8"},
    ],
}


SAMPLE_JSON_SYSTEM = {
    "@odata.context": "/redfish/v1/$metadata#Systems/Members/$entity",
    "@odata.id": "/redfish/v1/Systems/1",
    "@odata.type": "#ComputerSystem.1.1.0.ComputerSystem",
    "Id": "1",
    "Name": "Computer System",
    "SystemType": "Physical",
    "AssetTag": None,
    "Manufacturer": "Quanta",
    "Model": "F20A_HSW (To be filled by O.E.M.)",
    "SKU": None,
    "SerialNumber": "To be filled by O.E.M.",
    "PartNumber": None,
    "Description": "Computer System description",
    "UUID": "eac6520c-602c-2dbf-11e4-453b79c506e0",
    "HostName": None,
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "IndicatorLED": None,
    "PowerState": "On",
    "Boot": {
        "BootSourceOverrideEnabled": "Disabled",
        "BootSourceOverrideTarget": "None",
        "BootSourceOverrideTarget@Redfish.AllowableValues": ["Hdd", "Pxe"],
    },
    "BiosVersion": "F20A1A05_D",
    "ProcessorSummary": {
        "Count": 2,
        "Model": "Intel(R) Xeon(R) CPU E5-2695 v3 @ 2.30GHz",
        "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    },
    "MemorySummary": {
        "TotalSystemMemoryGiB": 30,
        "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    },
    "Processors": {"@odata.id": "/redfish/v1/Systems/1/Processors"},
    "EthernetInterfaces": {
        "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces"
    },
    "SimpleStorage": {"@odata.id": "/redfish/v1/Systems/1/SimpleStorage"},
    "Memory": {"@odata.id": "/redfish/v1/Systems/1/Memory"},
    "MemoryChunks": {"@odata.id": "/redfish/v1/Systems/1/MemoryChunks"},
    "Links": {
        "Chassis": [{"@odata.id": "/redfish/v1/Chassis/5"}],
        "ManagedBy": [{"@odata.id": "/redfish/v1/Managers/6"}],
        "Oem": {},
    },
    "Actions": {
        "#ComputerSystem.Reset": {
            "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
            "ResetType@Redfish.AllowableValues": [],
        },
        "Oem": {
            "Intel_RackScale": {
                "#ComputerSystem.StartDeepDiscovery": {"target": ""}
            }
        },
    },
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.ComputerSystem",
            "Adapters": {"@odata.id": "/redfish/v1/Systems/1/Adapters"},
            "PciDevices": [
                {"VendorId": "8086", "DeviceId": "2fd3"},
                {"VendorId": "8086", "DeviceId": "2f6f"},
            ],
            "DiscoveryState": "Deep",
            "ProcessorSockets": None,
            "MemorySockets": None,
        }
    },
}


SAMPLE_JSON_NODE = {
    "@odata.context": "/redfish/v1/$metadata#Nodes/Members/$entity",
    "@odata.id": "/redfish/v1/Nodes/1",
    "@odata.type": "#ComposedNode.1.0.0.ComposedNode",
    "Id": "1",
    "Name": "Test Node 1",
    "Description": None,
    "SystemType": "Logical",
    "AssetTag": None,
    "Manufacturer": "Quanta",
    "Model": "F20A_HSW (To be filled by O.E.M.)",
    "SKU": None,
    "SerialNumber": "To be filled by O.E.M.",
    "PartNumber": None,
    "UUID": "eac6520c-602c-2dbf-11e4-453b79c506e0",
    "HostName": None,
    "PowerState": "Off",
    "BiosVersion": "F20A1A05_D",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "Processors": {
        "Count": 2,
        "Model": "Intel(R) Xeon(R) CPU E5-2695 v3 @ 2.30GHz",
        "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    },
    "Memory": {
        "TotalSystemMemoryGiB": 30,
        "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    },
    "ComposedNodeState": "PoweredOff",
    "Boot": {
        "BootSourceOverrideEnabled": "Once",
        "BootSourceOverrideTarget": "Pxe",
        "BootSourceOverrideTarget@Redfish.AllowableValues": ["Hdd", "Pxe"],
    },
    "Oem": {},
    "Links": {
        "ComputerSystem": {"@odata.id": "/redfish/v1/Systems/1"},
        "Processors": [
            {"@odata.id": "/redfish/v1/Systems/1/Processors/1"},
            {"@odata.id": "/redfish/v1/Systems/1/Processors/2"},
        ],
        "Memory": [
            {"@odata.id": "/redfish/v1/Systems/1/Memory/1"},
            {"@odata.id": "/redfish/v1/Systems/1/Memory/2"},
            {"@odata.id": "/redfish/v1/Systems/1/Memory/3"},
            {"@odata.id": "/redfish/v1/Systems/1/Memory/4"},
        ],
        "EthernetInterfaces": [
            {"@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/4"},
            {"@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5"},
            {"@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/6"},
            {"@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/7"},
        ],
        "LocalDrives": [
            {"@odata.id": "/redfish/v1/Systems/1/Adapters/3/Devices/2"},
            {"@odata.id": "/redfish/v1/Systems/1/Adapters/3/Devices/3"},
        ],
        "RemoteDrives": [
            {"@odata.id": "/redfish/v1/Services/1/Targets/1"},
            {"@odata.id": "/redfish/v1/Services/1/Targets/2"},
        ],
        "ManagedBy": [{"@odata.id": "/redfish/v1/Managers/1"}],
        "Oem": {},
    },
    "Actions": {
        "#ComposedNode.Reset": {
            "target": "/redfish/v1/Nodes/1/Actions/ComposedNode.Reset",
            "ResetType@DMTF.AllowableValues": [],
        },
        "#ComposedNode.Assemble": {
            "target": "/redfish/v1/Nodes/1/Actions/ComposedNode.Assemble"
        },
    },
}


SAMPLE_JSON_PROCESSOR = {
    "@odata.id": "/redfish/v1/Systems/1/Processors/1",
    "@odata.type": "#Processor.1.0.0.Processor",
    "Name": "Processor",
    "Description": "Processor Description",
    "Id": "1",
    "Socket": "0",
    "ProcessorType": "CPU",
    "ProcessorArchitecture": "x86",
    "InstructionSet": "x86-64",
    "Manufacturer": "Intel Corp.",
    "Model": "Intel(R) Xeon(R) CPU E5-2695 v3 @ 2.30GHz",
    "ProcessorId": {
        "VendorId": "GenuineIntel",
        "IdentificationRegisters": "0",
        "EffectiveFamily": "6",
        "EffectiveModel": "63",
        "Step": "2",
        "MicrocodeInfo": "0x2d",
    },
    "MaxSpeedMHz": 2300,
    "TotalCores": 14,
    "TotalThreads": 28,
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": None},
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.Processor",
            "Brand": "E5",
            "ContainedBy": {"@odata.id": "/redfish/v1/Systems/1"},
        }
    },
}


SAMPLE_JSON_DEVICE = {
    "@odata.id": "/redfish/v1/Systems/1/Adapters/3/Devices/2",
    "@odata.type": "#Device.1.0.0.Device",
    "Id": "2",
    "Name": "Device",
    "Description": "Device description",
    "Interface": "SATA",
    "CapacityGiB": 111.7587089538574,
    "Type": "SSD",
    "RPM": None,
    "Manufacturer": "Intel",
    "Model": "INTEL_SSDMCEAC120B3",
    "SerialNumber": "CVLI310601PY120E",
    "FirmwareVersion": "LLLi",
    "BusInfo": "0.0.0",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": None},
    "Oem": {},
    "Links": {
        "ContainedBy": {"@odata.id": "/redfish/v1/Systems/1/Adapters/3"},
        "Oem": {},
    },
}


SAMPLE_JSON_INTERFACE = {
    "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5",
    "@odata.type": "#EthernetInterface.1.0.0.EthernetInterface",
    "Id": "5",
    "Name": "Ethernet Interface",
    "Description": "Ethernet Interface description",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": None},
    "InterfaceEnabled": True,
    "PermanentMACAddress": "54:ab:3a:36:af:45",
    "MACAddress": "54:ab:3a:36:af:45",
    "SpeedMbps": None,
    "AutoNeg": None,
    "FullDuplex": None,
    "MTUSize": None,
    "HostName": None,
    "FQDN": None,
    "VLANs": {"@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5/VLANs"},
    "IPv4Addresses": [],
    "IPv6AddressPolicyTable": [],
    "IPv6StaticAddresses": [],
    "MaxIPv6StaticAddresses": None,
    "IPv6DefaultGateway": None,
    "IPv6Addresses": [],
    "NameServers": [],
    "Oem": {},
    "Links": {
        "Oem": {
            "Intel_RackScale": {
                "@odata.type": "#Intel.Oem.EthernetInterface",
                "NeighborPort": {
                    "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2"
                },
            }
        }
    },
}


SAMPLE_JSON_PORT = {
    "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2",
    "@odata.type": "#EthernetSwitchPort.1.0.0.EthernetSwitchPort",
    "Id": "2",
    "Name": "Port29",
    "Description": "Ethernet Switch Port description",
    "PortId": "sw0p41",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "LinkType": "PCIe",
    "OperationalState": "Up",
    "AdministrativeState": "Up",
    "LinkSpeedMbps": 40000,
    "NeighborInfo": {"CableId": None, "PortId": None, "SwitchId": None},
    "NeighborMAC": "54:ab:3a:36:af:45",
    "FrameSize": 15358,
    "Autosense": False,
    "FullDuplex": None,
    "MACAddress": "54:ab:3a:36:af:45",
    "IPv4Addresses": [],
    "IPv6Addresses": [],
    "PortClass": "Physical",
    "PortMode": "Unknown",
    "PortType": "Downstream",
    "Oem": {},
    "VLANs": {"@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2/VLANs"},
    "Links": {
        "PrimaryVLAN": {
            "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2/VLANs/9"
        },
        "Switch": {"@odata.id": "/redfish/v1/EthernetSwitches/1"},
        "MemberOfPort": None,
        "PortMembers": [],
        "Oem": {
            "Intel_RackScale": {
                "@odata.type": "#Intel.Oem.EthernetSwitchPort",
                "NeighborInterface": {
                    "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5"
                },
            }
        },
    },
}


SAMPLE_JSON_VLAN = {
    "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2/VLANs/9",
    "@odata.type": "#VLanNetworkInterface.1.0.1.VLanNetworkInterface",
    "Id": "9",
    "Name": "VLAN1",
    "Description": "VLAN Network Interface description",
    "VLANEnable": True,
    "VLANId": 4088,
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.VLanNetworkInterface",
            "Tagged": False,
            "Status": {
                "State": "Enabled",
                "Health": "OK",
                "HealthRollup": None,
            },
        }
    },
}


SAMPLE_JSON_MEMORY = {
    "@odata.id": "/redfish/v1/Systems/1/Memory/1",
    "@odata.type": "#Memory.1.0.0.Memory",
    "Name": "Memory",
    "Id": "376",
    "Description": "Memory description",
    "MemoryType": "DRAM",
    "MemoryDeviceType": "DDR",
    "BaseModuleType": "RDIMM",
    "MemoryMedia": ["DRAM"],
    "CapacityMiB": 7812,
    "DataWidthBits": 64,
    "BusWidthBits": 72,
    "Manufacturer": "Micron",
    "SerialNumber": "0D861391",
    "PartNumber": "18ASF1G72PZ-2G1A2",
    "AllowedSpeedsMHz": [],
    "FirmwareRevision": None,
    "FirmwareApiVersion": None,
    "FunctionClasses": [],
    "VendorID": None,
    "DeviceID": None,
    "RankCount": None,
    "DeviceLocator": "B0",
    "MemoryLocation": None,
    "ErrorCorrection": None,
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": None},
    "OperatingSpeedMhz": 2133,
    "Regions": [
        {
            "RegionId": "0",
            "MemoryClassification": None,
            "OffsetMiB": 0,
            "SizeMiB": 7812,
        }
    ],
    "OperatingMemoryModes": [],
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.Memory",
            "VoltageVolt": 1.2,
        }
    },
}


SAMPLE_JSON_LVG = {
    "@odata.id": "/redfish/v1/Services/1/LogicalDrives/2",
    "@odata.type": "#LogicalDrive.1.0.0.LogicalDrive",
    "Id": "115",
    "Name": "Logical Drive",
    "Description": "Logical Drive description",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "Type": "LVM",
    "Mode": "LVG",
    "Protected": False,
    "CapacityGiB": 11178.140625,
    "Image": None,
    "Bootable": False,
    "Snapshot": False,
    "Links": {
        "LogicalDrives": [
            {"@odata.id": "/redfish/v1/Services/1/LogicalDrives/1"},
            {"@odata.id": "/redfish/v1/Services/1/LogicalDrives/3"},
            {"@odata.id": "/redfish/v1/Services/1/LogicalDrives/4"},
            {"@odata.id": "/redfish/v1/Services/1/LogicalDrives/5"},
        ],
        "PhysicalDrives": [],
        "UsedBy": [],
        "Targets": [],
    },
}

SAMPLE_JSON_LV = {
    "@odata.id": "/redfish/v1/Services/1/LogicalDrives/1",
    "@odata.type": "#LogicalDrive.1.0.0.LogicalDrive",
    "Id": "139",
    "Name": "Logical Drive",
    "Description": "Logical Drive description",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "Type": "LVM",
    "Mode": "LV",
    "Protected": False,
    "CapacityGiB": 80,
    "Image": None,
    "Bootable": True,
    "Snapshot": False,
    "Links": {
        "LogicalDrives": [],
        "PhysicalDrives": [],
        "MasterDrive": {"@odata.id": "/redfish/v1/Services/1/LogicalDrives/3"},
        "UsedBy": [{"@odata.id": "/redfish/v1/Services/1/LogicalDrives/2"}],
        "Targets": [
            {"@odata.id": "/redfish/v1/Services/1/Targets/1"},
            {"@odata.id": "/redfish/v1/Services/1/Targets/2"},
        ],
    },
}


SAMPLE_JSON_PV = {
    "@odata.id": "/redfish/v1/Services/8/LogicalDrives/126",
    "@odata.type": "#LogicalDrive.1.0.0.LogicalDrive",
    "Id": "126",
    "Name": "Logical Drive",
    "Description": "Logical Drive description",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "Type": "LVM",
    "Mode": "PV",
    "Protected": False,
    "CapacityGiB": 931.51171875,
    "Image": None,
    "Bootable": False,
    "Snapshot": False,
    "Links": {
        "LogicalDrives": [],
        "PhysicalDrives": [
            {"@odata.id": "/redfish/v1/Services/8/Drives/99"},
            {"@odata.id": "/redfish/v1/Services/8/Drives/103"},
        ],
        "UsedBy": [{"@odata.id": "/redfish/v1/Services/8/LogicalDrives/115"}],
        "Targets": [],
    },
}


SAMPLE_JSON_TARGET = {
    "@odata.id": "/redfish/v1/Services/1/Targets/1",
    "@odata.type": "#RemoteTarget.1.0.0.RemoteTarget",
    "Id": "19",
    "Name": "iSCSI Remote Target",
    "Description": "iSCSI Remote Target description",
    "Status": {"State": "Enabled", "Health": "OK", "HealthRollup": "OK"},
    "Type": None,
    "Addresses": [
        {
            "iSCSI": {
                "TargetLUN": [],
                "TargetIQN": "iqn.maas.io:test",
                "TargetPortalIP": "10.1.0.100",
                "TargetPortalPort": 3260,
            }
        }
    ],
    "Initiator": [{"iSCSI": {"InitiatorIQN": ""}}],
    "Oem": {},
    "Links": {"Oem": {}},
}


def make_context():
    return {
        "power_address": factory.make_ipv4_address(),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
        "node_id": factory.make_name("node_id"),
    }


def make_requested_machine(cores=None, cpu_speed=None, memory=None):
    if cores is None:
        cores = random.randint(2, 4)
    if cpu_speed is None:
        cpu_speed = random.randint(2000, 3000)
    if memory is None:
        memory = random.randint(1024, 4096)
    block_devices = [
        RequestedMachineBlockDevice(
            size=random.randint(1024 ** 3, 4 * 1024 ** 3)
        )
        for _ in range(3)
    ]
    interfaces = [RequestedMachineInterface() for _ in range(3)]
    return RequestedMachine(
        hostname=factory.make_name("hostname"),
        architecture="amd64/generic",
        cores=cores,
        memory=memory,
        cpu_speed=cpu_speed,
        block_devices=block_devices,
        interfaces=interfaces,
    )


def make_discovered_machine(
    hostname=None,
    cores=None,
    cpu_speed=None,
    memory=None,
    block_devices=[],
    interfaces=[],
):
    if hostname is None:
        hostname = factory.make_name("hostname")
    if cores is None:
        cores = random.randint(2, 4)
    if cpu_speed is None:
        cpu_speed = random.randint(2000, 3000)
    if memory is None:
        memory = random.randint(1024, 4096)
    if block_devices:
        block_devices = [
            DiscoveredMachineBlockDevice(
                model=factory.make_name("model"),
                serial=factory.make_name("serial"),
                size=random.randint(1024 ** 3, 4 * 1024 ** 3),
            )
            for _ in range(3)
        ]
    if interfaces:
        interfaces = [
            DiscoveredMachineInterface(mac_address=factory.make_mac_address())
            for _ in range(3)
        ]
    return DiscoveredMachine(
        hostname=hostname,
        architecture="amd64/generic",
        cores=cores,
        cpu_speed=cpu_speed,
        memory=memory,
        interfaces=interfaces,
        block_devices=block_devices,
        power_state=factory.make_name("unknown"),
        power_parameters={"node_id": factory.make_name("node_id")},
    )


def make_discovered_pod(
    cores=None, cpu_speed=None, memory=None, storage=None, disks=None
):
    if cores is None:
        cores = 8 * 4
    if cpu_speed is None:
        cpu_speed = 2000
    if memory is None:
        memory = 8192 * 4
    if storage is None:
        storage = 1024 * 3 * 4
    if disks is None:
        disks = 3 * 3 * 4
    machines = []
    cpu_speeds = [cpu_speed]
    for _ in range(3):
        machine = make_discovered_machine()
        machine.cpu_speeds = [machine.cpu_speed]
        machines.append(machine)
        cpu_speeds.append(machine.cpu_speed)
    discovered_pod = DiscoveredPod(
        architectures=[],
        cores=cores,
        cpu_speed=cpu_speed,
        memory=memory,
        local_storage=storage,
        hints=DiscoveredPodHints(
            cores=0, cpu_speed=0, memory=0, local_storage=0, local_disks=0
        ),
        machines=machines,
        local_disks=disks,
    )
    # Add cpu_speeds to the DiscoveredPod.
    discovered_pod.cpu_speeds = cpu_speeds
    return discovered_pod


class TestRSDPodDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = RSDPodDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    @inlineCallbacks
    def test_list_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        endpoint = factory.make_name("endpoint")
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_SYSTEMS, None)
        expected_data = SAMPLE_JSON_SYSTEMS
        members = expected_data.get("Members")
        resource_ids = []
        for resource in members:
            resource_ids.append(
                resource["@odata.id"].lstrip("/").encode("utf-8")
            )
        resources = yield driver.list_resources(endpoint, headers)
        self.assertItemsEqual(resources, resource_ids)

    @inlineCallbacks
    def test_scrape_logical_drives_and_targets(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        lv_link = b"redfish/v1/Services/1/LogicalDrives/%s"
        target_link = b"redfish/v1/Services/1/Targets/%s"
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.side_effect = [
            [b"redfish/v1/Services/1"],
            [lv_link % b"1", lv_link % b"3"],
            [target_link % b"1", target_link % b"2"],
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.side_effect = [
            (SAMPLE_JSON_LV, None),
            (SAMPLE_JSON_PV, None),
            (SAMPLE_JSON_TARGET, None),
            (SAMPLE_JSON_TARGET, None),
        ]

        (
            logical_drives,
            targets,
        ) = yield driver.scrape_logical_drives_and_targets(url, headers)
        self.assertDictEqual(
            logical_drives,
            {lv_link % b"1": SAMPLE_JSON_LV, lv_link % b"3": SAMPLE_JSON_PV},
        )
        self.assertDictEqual(
            targets,
            {
                target_link % b"1": SAMPLE_JSON_TARGET,
                target_link % b"2": SAMPLE_JSON_TARGET,
            },
        )

    @inlineCallbacks
    def test_scrape_remote_drives(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.return_value = [b"redfish/v1/Nodes/1"]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_NODE, None)

        remote_drives = yield driver.scrape_remote_drives(url, headers)
        self.assertEqual(
            {
                "/redfish/v1/Services/1/Targets/1",
                "/redfish/v1/Services/1/Targets/2",
            },
            remote_drives,
        )

    def test_calculate_remote_storage(self):
        driver = RSDPodDriver()
        LV_NO_TARGETS = deepcopy(SAMPLE_JSON_LV)
        LV_NO_TARGETS["Links"]["Targets"] = []
        logical_drives = {
            b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
            b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            b"redfish/v1/Services/1/LogicalDrives/3": LV_NO_TARGETS,
            b"redfish/v1/Services/1/LogicalDrives/4": SAMPLE_JSON_PV,
            b"redfish/v1/Services/1/LogicalDrives/5": SAMPLE_JSON_PV,
        }
        targets = {
            b"redfish/v1/Services/1/Targets/1": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/2": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/3": SAMPLE_JSON_TARGET,
        }
        remote_drives = set(b"/redfish/v1/Services/1/Targets/1")

        remote_storage = driver.calculate_remote_storage(
            remote_drives, logical_drives, targets
        )
        self.assertDictEqual(
            remote_storage,
            {
                b"redfish/v1/Services/1/LogicalDrives/2": {
                    "total": 11830638411776.0,
                    "available": 11830638411776.0,
                    "master": {
                        "path": b"/redfish/v1/Services/1/LogicalDrives/1",
                        "size": 80,
                    },
                }
            },
        )

    def test_calculate_remote_storage_no_remote_drives(self):
        driver = RSDPodDriver()
        LV_NO_TARGETS = deepcopy(SAMPLE_JSON_LV)
        LV_NO_TARGETS["Links"]["Targets"] = []
        logical_drives = {
            b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
            b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            b"redfish/v1/Services/1/LogicalDrives/3": LV_NO_TARGETS,
            b"redfish/v1/Services/1/LogicalDrives/4": SAMPLE_JSON_PV,
            b"redfish/v1/Services/1/LogicalDrives/5": SAMPLE_JSON_PV,
        }
        targets = {
            b"redfish/v1/Services/1/Targets/1": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/2": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/3": SAMPLE_JSON_TARGET,
        }
        # Test when no remote drives are in use.
        remote_drives = set()

        remote_storage = driver.calculate_remote_storage(
            remote_drives, logical_drives, targets
        )
        self.assertDictEqual(
            remote_storage,
            {
                b"redfish/v1/Services/1/LogicalDrives/2": {
                    "total": 11830638411776.0,
                    "available": 11830638411776.0,
                    "master": {
                        "path": b"/redfish/v1/Services/1/LogicalDrives/1",
                        "size": 80,
                    },
                }
            },
        )

    def test_calculate_pod_remote_storage(self):
        driver = RSDPodDriver()
        logical_drives = {
            b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
            b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            b"redfish/v1/Services/1/LogicalDrives/3": SAMPLE_JSON_LV,
        }
        remote_storage = {
            b"redfish/v1/Services/1/LogicalDrives/1": {
                "total": 80 * (1024 ** 3),
                "available": None,
                "master": {"path": None, "size": None},
            },
            b"redfish/v1/Services/1/LogicalDrives/2": {
                "total": 12 * (1024 ** 3),
                "available": None,
                "master": {"path": None, "size": None},
            },
        }
        mock_calculate_remote_storage = self.patch(
            driver, "calculate_remote_storage"
        )
        mock_calculate_remote_storage.return_value = remote_storage

        pod_capacity, pod_hints_capacity = driver.calculate_pod_remote_storage(
            factory.make_name("remote_drives"),
            logical_drives,
            factory.make_name("targets"),
        )
        self.assertEqual(92 * (1024 ** 3), pod_capacity)
        self.assertEqual(80 * (1024 ** 3), pod_hints_capacity)

    @inlineCallbacks
    def test_get_pod_memory_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.return_value = [
            b"redfish/v1/Systems/1/Memory/1",
            b"redfish/v1/Systems/1/Memory/2",
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.side_effect = [
            (SAMPLE_JSON_MEMORY, None),
            (SAMPLE_JSON_MEMORY, None),
        ]

        memories = yield driver.get_pod_memory_resources(url, headers, system)
        self.assertEqual([7812, 7812], memories)

    @inlineCallbacks
    def test_get_pod_processor_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.return_value = [
            b"redfish/v1/Systems/1/Processors/1",
            b"redfish/v1/Systems/1/Processors/2",
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.side_effect = [
            (SAMPLE_JSON_PROCESSOR, None),
            (SAMPLE_JSON_PROCESSOR, None),
        ]

        cores, cpu_speeds, arch = yield driver.get_pod_processor_resources(
            url, headers, system
        )
        self.assertEqual([28, 28], cores)
        self.assertEqual([2300, 2300], cpu_speeds)
        self.assertEqual("x86-64", arch)

    @inlineCallbacks
    def test_get_pod_storage_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.side_effect = [
            [b"redfish/v1/Systems/1/Adapters/3"],
            [
                b"redfish/v1/Systems/1/Adapters/3/Devices/2",
                b"redfish/v1/Systems/1/Adapters/3/Devices/3",
            ],
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.side_effect = [
            (SAMPLE_JSON_DEVICE, None),
            (SAMPLE_JSON_DEVICE, None),
        ]

        storages = yield driver.get_pod_storage_resources(url, headers, system)
        self.assertEqual([111.7587089538574, 111.7587089538574], storages)

    @inlineCallbacks
    def test_get_pod_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.side_effect = [
            [b"redfish/v1/Systems/1", b"redfish/v1/Systems/2"],
            [b"redfish/v1/Systems/1/Memory/1"],
            [b"redfish/v1/Systems/1/Processors/1"],
            [b"redfish/v1/Systems/1/Adapters/3"],
            [b"redfish/v1/Systems/1/Adapters/3/Devices/2"],
            [b"redfish/v1/Systems/1/Memory/1"],
            [b"redfish/v1/Systems/1/Processors/1"],
            [b"redfish/v1/Systems/1/Adapters/3"],
            [b"redfish/v1/Systems/1/Adapters/3/Devices/2"],
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.side_effect = [
            (SAMPLE_JSON_MEMORY, None),
            (SAMPLE_JSON_PROCESSOR, None),
            (SAMPLE_JSON_DEVICE, None),
            (SAMPLE_JSON_MEMORY, None),
            (SAMPLE_JSON_PROCESSOR, None),
            (SAMPLE_JSON_DEVICE, None),
        ]

        pod = yield driver.get_pod_resources(url, headers)
        self.assertEqual(["amd64/generic"], pod.architectures)
        self.assertEqual(28 * 2, pod.cores)
        self.assertEqual(2300, pod.cpu_speed)
        self.assertEqual(7812 * 2, pod.memory)
        self.assertEqual(119999999999.99997 * 2, pod.local_storage)
        self.assertEqual(2, pod.local_disks)
        self.assertEqual(
            [Capabilities.COMPOSABLE, Capabilities.FIXED_LOCAL_STORAGE],
            pod.capabilities,
        )

    @inlineCallbacks
    def test_get_pod_resources_skips_invalid_systems(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.side_effect = [
            [b"redfish/v1/Systems/1"],
            [b"redfish/v1/Systems/1/Processors/1"],
            [b"redfish/v1/Systems/1/Adapters/3"],
            [b"redfish/v1/Systems/1/Adapters/3/Devices/2"],
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_get_pod_memory_resources = self.patch(
            driver, "get_pod_memory_resources"
        )
        mock_get_pod_memory_resources.return_value = [None]
        mock_redfish_request.side_effect = [
            (SAMPLE_JSON_SYSTEM, None),
            (SAMPLE_JSON_PROCESSOR, None),
            (SAMPLE_JSON_DEVICE, None),
        ]

        pod = yield driver.get_pod_resources(url, headers)
        self.assertEqual(0, pod.cores)
        self.assertEqual(0, pod.cpu_speed)
        self.assertEqual(0, pod.memory)
        self.assertEqual(0, pod.local_storage)

    @inlineCallbacks
    def test_get_pod_machine_memories(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        node_data = SAMPLE_JSON_NODE
        discovered_machine = make_discovered_machine(memory=0)
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_MEMORY, None)

        yield driver.get_pod_machine_memories(
            node_data, url, headers, discovered_machine
        )
        self.assertEqual(31248, discovered_machine.memory)

    @inlineCallbacks
    def test_get_pod_machine_processors(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        node_data = SAMPLE_JSON_NODE
        discovered_machine = make_discovered_machine(cores=0, cpu_speed=0)
        discovered_machine.cpu_speeds = []
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_PROCESSOR, None)

        yield driver.get_pod_machine_processors(
            node_data, url, headers, discovered_machine
        )
        self.assertEqual("amd64/generic", discovered_machine.architecture)
        self.assertEqual(56, discovered_machine.cores)
        self.assertEqual([2300, 2300], discovered_machine.cpu_speeds)

    @inlineCallbacks
    def test_get_pod_machine_local_storages(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        node_data = SAMPLE_JSON_NODE
        discovered_machine = make_discovered_machine(block_devices=[])
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_DEVICE, None)

        yield driver.get_pod_machine_local_storages(
            node_data, url, headers, discovered_machine
        )
        self.assertThat(
            discovered_machine.block_devices,
            MatchesListwise(
                [
                    MatchesStructure(
                        model=Equals("INTEL_SSDMCEAC120B3"),
                        serial=Equals("CVLI310601PY120E"),
                        size=Equals(119999999999.99997),
                        block_size=Equals(512),
                        tags=Equals(["local", "ssd"]),
                        type=Equals(BlockDeviceType.PHYSICAL),
                    ),
                    MatchesStructure(
                        model=Equals("INTEL_SSDMCEAC120B3"),
                        serial=Equals("CVLI310601PY120E"),
                        size=Equals(119999999999.99997),
                        block_size=Equals(512),
                        tags=Equals(["local", "ssd"]),
                        type=Equals(BlockDeviceType.PHYSICAL),
                    ),
                ]
            ),
        )

    @inlineCallbacks
    def test_get_pod_machine_local_storages_with_request(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        request = make_requested_machine()
        # Set the tags on the requested machine's block devices
        # and the size.  First device will be a device that has
        # its tags mapped, while the second one will be at a size
        # that is bigger than the available local disk size so its
        # tags will not be mapped.
        request.block_devices[0].size = 100 * 1024 ** 3
        request.block_devices[0].tags = ["local", "tags mapped"]
        request.block_devices[1].size = 200 * 1024 ** 3
        request.block_devices[1].tags = ["local", "tags not mapped"]
        local_drive = "/redfish/v1/Systems/1/Adapters/3/Devices/3"
        node_data = SAMPLE_JSON_NODE
        discovered_machine = make_discovered_machine(block_devices=[])
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_DEVICE, None)
        self.patch_autospec(rsd_module.maaslog, "warning")

        yield driver.get_pod_machine_local_storages(
            node_data, url, headers, discovered_machine, request
        )
        self.assertThat(
            discovered_machine.block_devices,
            MatchesListwise(
                [
                    MatchesStructure(
                        model=Equals("INTEL_SSDMCEAC120B3"),
                        serial=Equals("CVLI310601PY120E"),
                        size=Equals(119999999999.99997),
                        block_size=Equals(512),
                        tags=Equals(["local", "tags mapped", "ssd"]),
                        type=Equals(BlockDeviceType.PHYSICAL),
                    ),
                    MatchesStructure(
                        model=Equals("INTEL_SSDMCEAC120B3"),
                        serial=Equals("CVLI310601PY120E"),
                        size=Equals(119999999999.99997),
                        block_size=Equals(512),
                        tags=Equals(["local", "ssd"]),
                        type=Equals(BlockDeviceType.PHYSICAL),
                    ),
                ]
            ),
        )
        self.assertThat(
            rsd_module.maaslog.warning,
            MockCalledOnceWith(
                "Requested disk size is larger than %d GiB, which "
                "drive '%r' contains.  RSD allocation should have "
                "failed.  Please report this to your RSD Pod "
                "administrator."
                % (
                    discovered_machine.block_devices[1].size / (1024 ** 3),
                    local_drive,
                )
            ),
        )

    def test_get_pod_machine_remote_storages(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        discovered_machine = make_discovered_machine(block_devices=[])
        node_data = deepcopy(SAMPLE_JSON_NODE)
        node_data["Links"]["RemoteDrives"].append(
            {"@odata.id": "/redfish/v1/Services/1/Targets/3"}
        )
        LV_CHANGED = deepcopy(SAMPLE_JSON_LV)
        LV_CHANGED["Links"]["Targets"].append(
            {"@odata.id": "/redfish/v1/Services/1/Targets/3"}
        )
        TARGET_CHANGED_1 = deepcopy(SAMPLE_JSON_TARGET)
        TARGET_CHANGED_2 = deepcopy(SAMPLE_JSON_TARGET)
        TARGET_CHANGED_1["Addresses"][0]["iSCSI"]["TargetLUN"].append(
            {"LUN": 3}
        )
        TARGET_CHANGED_2["Initiator"][0]["iSCSI"]["InitiatorIQN"] = "ALL"
        remote_drives = set(
            [
                "/redfish/v1/Services/1/Targets/1",
                "/redfish/v1/Services/1/Targets/2",
                "/redfish/v1/Services/1/Targets/3",
            ]
        )
        logical_drives = {
            b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
            b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            b"redfish/v1/Services/1/LogicalDrives/3": LV_CHANGED,
        }
        targets = {
            b"redfish/v1/Services/1/Targets/1": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/2": TARGET_CHANGED_1,
            b"redfish/v1/Services/1/Targets/3": TARGET_CHANGED_2,
        }

        driver.get_pod_machine_remote_storages(
            node_data,
            url,
            headers,
            remote_drives,
            logical_drives,
            targets,
            discovered_machine,
        )
        self.assertEqual(
            set(
                [
                    "/redfish/v1/Services/1/Targets/1",
                    "/redfish/v1/Services/1/Targets/2",
                ]
            ),
            remote_drives,
        )
        self.assertEqual(
            {
                b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
                b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            },
            logical_drives,
        )
        self.assertEqual(
            {
                b"redfish/v1/Services/1/Targets/1": SAMPLE_JSON_TARGET,
                b"redfish/v1/Services/1/Targets/2": TARGET_CHANGED_1,
            },
            targets,
        )
        self.assertThat(
            discovered_machine.block_devices,
            MatchesListwise(
                [
                    MatchesStructure(
                        model=Is(None),
                        serial=Is(None),
                        size=Equals(85899345920.0),
                        block_size=Equals(512),
                        tags=Equals(["iscsi"]),
                        type=Equals(BlockDeviceType.ISCSI),
                        iscsi_target=Equals(
                            "10.1.0.100:6:3260:0:iqn.maas.io:test"
                        ),
                    ),
                    MatchesStructure(
                        model=Is(None),
                        serial=Is(None),
                        size=Equals(85899345920.0),
                        block_size=Equals(512),
                        tags=Equals(["iscsi"]),
                        type=Equals(BlockDeviceType.ISCSI),
                        iscsi_target=Equals(
                            "10.1.0.100:6:3260:3:iqn.maas.io:test"
                        ),
                    ),
                ]
            ),
        )

    def test_get_pod_machine_remote_storages_with_request(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        request = make_requested_machine()
        # Set the tags on the requested machine's block devices
        # and the iscsi_target.
        for idx in range(3):
            request.block_devices[idx].tags = ["testing tags %d" % idx]
            request.block_devices[idx].iscsi_target = "iqn.maas.io:test"
        node_data = SAMPLE_JSON_NODE
        discovered_machine = make_discovered_machine(block_devices=[])
        TARGET_CHANGED = deepcopy(SAMPLE_JSON_TARGET)
        TARGET_CHANGED["Addresses"][0]["iSCSI"]["TargetLUN"].append({"LUN": 3})
        remote_drives = set(b"/redfish/v1/Services/1/Targets/1")
        logical_drives = {
            b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
            b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            b"redfish/v1/Services/1/LogicalDrives/3": SAMPLE_JSON_LV,
        }
        targets = {
            b"redfish/v1/Services/1/Targets/1": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/2": TARGET_CHANGED,
        }

        driver.get_pod_machine_remote_storages(
            node_data,
            url,
            headers,
            remote_drives,
            logical_drives,
            targets,
            discovered_machine,
            request,
        )
        self.assertThat(
            discovered_machine.block_devices,
            MatchesListwise(
                [
                    MatchesStructure(
                        model=Is(None),
                        serial=Is(None),
                        size=Equals(85899345920.0),
                        block_size=Equals(512),
                        tags=Equals(["testing tags 2", "iscsi"]),
                        type=Equals(BlockDeviceType.ISCSI),
                        iscsi_target=Equals(
                            "10.1.0.100:6:3260:0:iqn.maas.io:test"
                        ),
                    ),
                    MatchesStructure(
                        model=Is(None),
                        serial=Is(None),
                        size=Equals(85899345920.0),
                        block_size=Equals(512),
                        tags=Equals(["testing tags 1", "iscsi"]),
                        type=Equals(BlockDeviceType.ISCSI),
                        iscsi_target=Equals(
                            "10.1.0.100:6:3260:3:iqn.maas.io:test"
                        ),
                    ),
                ]
            ),
        )

    @inlineCallbacks
    def test_get_pod_machine_interfaces(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        node_data = SAMPLE_JSON_NODE
        discovered_machine = make_discovered_machine()
        mock_redfish_request = self.patch(driver, "redfish_request")
        NIC1_DATA = deepcopy(SAMPLE_JSON_INTERFACE)
        NIC1_DATA["SpeedMbps"] = 900
        NIC2_DATA = deepcopy(SAMPLE_JSON_INTERFACE)
        NIC2_DATA["SpeedMbps"] = 1000
        NIC3_DATA = deepcopy(SAMPLE_JSON_INTERFACE)
        NIC3_DATA["SpeedMbps"] = 2000
        NIC4_DATA = deepcopy(SAMPLE_JSON_INTERFACE)
        NIC4_DATA["Links"]["Oem"] = None
        mock_redfish_request.side_effect = [
            (NIC1_DATA, None),
            (SAMPLE_JSON_PORT, None),
            (SAMPLE_JSON_VLAN, None),
            (NIC2_DATA, None),
            (SAMPLE_JSON_PORT, None),
            (SAMPLE_JSON_VLAN, None),
            (NIC3_DATA, None),
            (SAMPLE_JSON_PORT, None),
            (SAMPLE_JSON_VLAN, None),
            (NIC4_DATA, None),
            (SAMPLE_JSON_PORT, None),
            (SAMPLE_JSON_VLAN, None),
        ]

        yield driver.get_pod_machine_interfaces(
            node_data, url, headers, discovered_machine
        )
        self.assertThat(
            discovered_machine.interfaces,
            MatchesListwise(
                [
                    MatchesStructure(
                        mac_address=Equals("54:ab:3a:36:af:45"),
                        vid=Equals(4088),
                        tags=Equals(["e900"]),
                        boot=Equals(False),
                    ),
                    MatchesStructure(
                        mac_address=Equals("54:ab:3a:36:af:45"),
                        vid=Equals(4088),
                        tags=Equals(["1g", "e1000"]),
                        boot=Equals(False),
                    ),
                    MatchesStructure(
                        mac_address=Equals("54:ab:3a:36:af:45"),
                        vid=Equals(4088),
                        tags=Equals(["2.0"]),
                        boot=Equals(False),
                    ),
                    MatchesStructure(
                        mac_address=Equals("54:ab:3a:36:af:45"),
                        vid=Equals(-1),
                        tags=Equals([]),
                        boot=Equals(True),
                    ),
                ]
            ),
        )

    @inlineCallbacks
    def test_get_pod_machine(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        request = make_requested_machine()
        discovered_machine = DiscoveredMachine(
            architecture="amd64/generic",
            cores=0,
            cpu_speed=0,
            memory=0,
            interfaces=[],
            block_devices=[],
            power_parameters={"node_id": "1"},
        )
        node_data = SAMPLE_JSON_NODE
        TARGET_CHANGED = deepcopy(SAMPLE_JSON_TARGET)
        TARGET_CHANGED["Addresses"][0]["iSCSI"]["TargetLUN"].append({"LUN": 3})
        remote_drives = set(b"/redfish/v1/Services/1/Targets/1")
        logical_drives = {
            b"redfish/v1/Services/1/LogicalDrives/1": SAMPLE_JSON_LV,
            b"redfish/v1/Services/1/LogicalDrives/2": SAMPLE_JSON_LVG,
            b"redfish/v1/Services/1/LogicalDrives/3": SAMPLE_JSON_LV,
        }
        targets = {
            b"redfish/v1/Services/1/Targets/1": SAMPLE_JSON_TARGET,
            b"redfish/v1/Services/1/Targets/2": TARGET_CHANGED,
        }
        mock_discovered_machine = self.patch(driver, "DiscoveredMachine")
        mock_discovered_machine.return_value = discovered_machine
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (node_data, None)
        mock_get_pod_machine_memories = self.patch(
            driver, "get_pod_machine_memories"
        )
        mock_get_pod_machine_processors = self.patch(
            driver, "get_pod_machine_processors"
        )
        mock_get_pod_machine_local_storages = self.patch(
            driver, "get_pod_machine_local_storages"
        )
        mock_get_pod_machine_remote_storages = self.patch(
            driver, "get_pod_machine_remote_storages"
        )
        mock_get_pod_machine_interfaces = self.patch(
            driver, "get_pod_machine_interfaces"
        )

        machine = yield driver.get_pod_machine(
            b"redfish/v1/Nodes/1",
            url,
            headers,
            remote_drives,
            logical_drives,
            targets,
            request,
        )
        self.assertEqual(node_data["Name"], machine.hostname)
        self.assertEqual(
            RSD_SYSTEM_POWER_STATE.get(node_data["PowerState"]),
            machine.power_state,
        )
        self.assertThat(
            mock_get_pod_machine_memories,
            MockCalledOnceWith(node_data, url, headers, machine),
        )
        self.assertThat(
            mock_get_pod_machine_processors,
            MockCalledOnceWith(node_data, url, headers, machine),
        )
        self.assertThat(
            mock_get_pod_machine_local_storages,
            MockCalledOnceWith(node_data, url, headers, machine, request),
        )
        self.assertThat(
            mock_get_pod_machine_remote_storages,
            MockCalledOnceWith(
                node_data,
                url,
                headers,
                remote_drives,
                logical_drives,
                targets,
                machine,
                request,
            ),
        )
        self.assertThat(
            mock_get_pod_machine_interfaces,
            MockCalledOnceWith(node_data, url, headers, machine),
        )

    @inlineCallbacks
    def test_get_pod_machines(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        remote_drives = set(b"redfish/v1/Services/1/Targets/1")
        logical_drives = {
            factory.make_name("lv_path"): factory.make_name("lv_data")
            for _ in range(3)
        }
        targets = {
            factory.make_name("target_path"): factory.make_name("target_data")
            for _ in range(3)
        }
        mock_list_resources = self.patch(driver, "list_resources")
        mock_list_resources.side_effect = [
            [b"redfish/v1/Nodes/1"],
            [b"redfish/v1/Systems/1/Memory/1"],
            [b"redfish/v1/Systems/1/Processors/1"],
            [b"redfish/v1/Systems/1/Adapters/3"],
            [b"redfish/v1/Systems/1/Adapters/3/Devices/2"],
            [b"redfish/v1/Systems/1/EthernetInterfaces/5"],
        ]
        expected_machines = [make_discovered_machine for _ in range(3)]
        mock_get_pod_machine = self.patch(driver, "get_pod_machine")
        mock_get_pod_machine.return_value = expected_machines

        discovered_machines = yield driver.get_pod_machines(
            url, headers, remote_drives, logical_drives, targets
        )
        self.assertEqual(1, len(discovered_machines))
        self.assertThat(
            mock_get_pod_machine,
            MockCalledOnceWith(
                b"redfish/v1/Nodes/1",
                url,
                headers,
                remote_drives,
                logical_drives,
                targets,
                None,
            ),
        )

    def test_get_pod_hints(self):
        driver = RSDPodDriver()
        discovered_pod = make_discovered_pod()
        # Calculate expected hints.
        used_cores = used_memory = used_storage = used_disks = 0
        for machine in discovered_pod.machines:
            used_cores += machine.cores
            used_memory += machine.memory
            for blk_dev in machine.block_devices:
                used_storage += blk_dev.size
                used_disks += 1

        expected_cpu_speed = discovered_pod.cpu_speed
        expected_cores = discovered_pod.cores - used_cores
        expected_memory = discovered_pod.memory - used_memory
        expected_local_storage = discovered_pod.local_storage - used_storage
        expected_local_disks = discovered_pod.local_disks - used_disks

        discovered_pod_hints = driver.get_pod_hints(discovered_pod)
        self.assertEqual(expected_cpu_speed, discovered_pod_hints.cpu_speed)
        self.assertEqual(expected_cores, discovered_pod_hints.cores)
        self.assertEqual(expected_memory, discovered_pod_hints.memory)
        self.assertEqual(
            expected_local_storage, discovered_pod_hints.local_storage
        )
        self.assertEqual(
            expected_local_disks, discovered_pod_hints.local_disks
        )

    @inlineCallbacks
    def test_discover(self):
        driver = RSDPodDriver()
        context = make_context()
        headers = driver.make_auth_headers(**context)
        url = driver.get_url(context)
        remote_drives = factory.make_name("remote_drive")
        logical_drives = factory.make_name("logical_drives")
        targets = factory.make_name("targets")
        pod_iscsi_capacity = random.randint(10 * 1024 ** 3, 20 * 1024 ** 3)
        pod_hints_iscsi_capacity = random.randint(
            10 * 1024 ** 3, 20 * 1024 ** 3
        )
        mock_scrape_logical_drives_and_targets = self.patch(
            driver, "scrape_logical_drives_and_targets"
        )
        mock_scrape_logical_drives_and_targets.return_value = (
            logical_drives,
            targets,
        )
        mock_scrape_remote_drives = self.patch(driver, "scrape_remote_drives")
        mock_scrape_remote_drives.return_value = remote_drives
        mock_calculate_pod_remote_storage = self.patch(
            driver, "calculate_pod_remote_storage"
        )
        mock_calculate_pod_remote_storage.return_value = (
            pod_iscsi_capacity,
            pod_hints_iscsi_capacity,
        )
        mock_get_pod_resources = self.patch(driver, "get_pod_resources")
        mock_get_pod_machines = self.patch(driver, "get_pod_machines")
        mock_get_pod_hints = self.patch(driver, "get_pod_hints")

        discovered_pod = yield driver.discover(
            factory.make_name("system_id"), context
        )
        self.assertEqual(pod_iscsi_capacity, discovered_pod.iscsi_storage)
        self.assertEqual(
            pod_hints_iscsi_capacity, discovered_pod.hints.iscsi_storage
        )
        self.assertThat(
            mock_scrape_logical_drives_and_targets,
            MockCalledOnceWith(url, headers),
        )
        self.assertThat(
            mock_scrape_remote_drives, MockCalledOnceWith(url, headers)
        )
        self.assertThat(
            mock_calculate_pod_remote_storage,
            MockCalledOnceWith(remote_drives, logical_drives, targets),
        )
        self.assertThat(
            mock_get_pod_resources, MockCalledOnceWith(url, headers)
        )
        self.assertThat(
            mock_get_pod_machines,
            MockCalledOnceWith(
                url, headers, remote_drives, logical_drives, targets
            ),
        )
        self.assertThat(
            mock_get_pod_hints,
            MockCalledOnceWith(mock_get_pod_resources.return_value),
        )

    def test_select_remote_master(self):
        driver = RSDPodDriver()
        size = 20 * (1024 ** 3)
        remote_storage = {
            b"redfish/v1/Services/1/LogicalDrives/1": {
                "total": 80 * (1024 ** 3),
                "available": 50 * (1024 ** 3),
                "master": {
                    "path": b"redfish/v1/Services/1/LogicalDrives/2",
                    "size": 10 * (1024 ** 3),
                },
            }
        }

        master = driver.select_remote_master(remote_storage, size)
        self.assertEqual(
            remote_storage[b"redfish/v1/Services/1/LogicalDrives/1"][
                "available"
            ],
            50 * (1024 ** 3) - size,
        )
        self.assertThat(
            master,
            MatchesDict(
                {
                    "path": Equals(b"redfish/v1/Services/1/LogicalDrives/2"),
                    "size": Equals(10 * (1024 ** 3)),
                }
            ),
        )

    def test_set_drive_type(self):
        driver = RSDPodDriver()
        local_drive = {
            "CapacityGiB": None,
            "Type": None,
            "MinRPM": None,
            "SerialNumber": None,
            "Interface": None,
        }
        bk_types = ["SSD", "NVMe", "HDD"]
        for idx, bk_type in enumerate(["ssd", "nvme", "hdd"]):
            block_device = RequestedMachineBlockDevice(
                size=random.randint(1024 ** 3, 4 * 1024 ** 3), tags=[bk_type]
            )
            drive = local_drive.copy()
            driver.set_drive_type(drive, block_device)
            self.assertEqual(drive["Type"], bk_types[idx])

    def test_convert_request_to_json_payload(self):
        driver = RSDPodDriver()
        request = make_requested_machine()
        # iSCSI disk smaller than master drive size of 10GiB.
        request.block_devices[1].tags.append("iscsi")
        request.block_devices[1].size = 9 * (1024 ** 3)
        # iSCSI disk larger than master drive size of 10GiB.
        request.block_devices[2].size = 15 * (1024 ** 3)
        processors = 2
        cores = request.cores / 2
        remote_storage = {
            b"redfish/v1/Services/1/LogicalDrives/1": {
                "total": 80 * (1024 ** 3),
                "available": 40 * (1024 ** 3),
                "master": {
                    "path": b"redfish/v1/Services/1/LogicalDrives/2",
                    "size": 10,
                },
            }
        }

        mock_calculate_remote_storage = self.patch(
            driver, "calculate_remote_storage"
        )
        mock_calculate_remote_storage.return_value = remote_storage
        payload = driver.convert_request_to_json_payload(
            processors, cores, request, None, None, None
        )
        self.assertThat(
            json.loads(payload.decode("utf-8")),
            MatchesDict(
                {
                    "Name": Equals(request.hostname),
                    "Processors": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "Model": Equals(None),
                                    "TotalCores": Equals(cores),
                                    "AchievableSpeedMHz": Equals(
                                        request.cpu_speed
                                    ),
                                    "InstructionSet": Equals("x86-64"),
                                }
                            ),
                            MatchesDict(
                                {
                                    "Model": Equals(None),
                                    "TotalCores": Equals(cores),
                                    "AchievableSpeedMHz": Equals(
                                        request.cpu_speed
                                    ),
                                    "InstructionSet": Equals("x86-64"),
                                }
                            ),
                        ]
                    ),
                    "Memory": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "SpeedMHz": Equals(None),
                                    "CapacityMiB": Equals(request.memory),
                                    "DataWidthBits": Equals(None),
                                }
                            )
                        ]
                    ),
                    "EthernetInterfaces": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "SpeedMbps": Equals(None),
                                    "PrimaryVLAN": Equals(None),
                                }
                            ),
                            MatchesDict(
                                {
                                    "SpeedMbps": Equals(None),
                                    "PrimaryVLAN": Equals(None),
                                }
                            ),
                            MatchesDict(
                                {
                                    "SpeedMbps": Equals(None),
                                    "PrimaryVLAN": Equals(None),
                                }
                            ),
                        ]
                    ),
                    "LocalDrives": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "SerialNumber": Equals(None),
                                    "Type": Equals(None),
                                    "CapacityGiB": Equals(
                                        request.block_devices[0].size
                                        / (1024 ** 3)
                                    ),
                                    "MinRPM": Equals(None),
                                    "Interface": Equals(None),
                                }
                            )
                        ]
                    ),
                    "RemoteDrives": MatchesListwise(
                        [
                            MatchesDict(
                                {
                                    "Master": MatchesDict(
                                        {
                                            "Resource": MatchesDict(
                                                {
                                                    "@odata.id": Equals(
                                                        "redfish/v1/Services/1/LogicalDrives/2"
                                                    )
                                                }
                                            ),
                                            "Type": Equals("Snapshot"),
                                        }
                                    ),
                                    "CapacityGiB": Equals(10),
                                    "iSCSIAddress": Equals(
                                        "iqn.2010-08.io.maas:"
                                        + request.hostname
                                        + "-1"
                                    ),
                                }
                            ),
                            MatchesDict(
                                {
                                    "Master": MatchesDict(
                                        {
                                            "Resource": MatchesDict(
                                                {
                                                    "@odata.id": Equals(
                                                        "redfish/v1/Services/1/LogicalDrives/2"
                                                    )
                                                }
                                            ),
                                            "Type": Equals("Snapshot"),
                                        }
                                    ),
                                    "CapacityGiB": Equals(
                                        request.block_devices[2].size
                                        / (1024 ** 3)
                                    ),
                                    "iSCSIAddress": Equals(
                                        "iqn.2010-08.io.maas:"
                                        + request.hostname
                                        + "-2"
                                    ),
                                }
                            ),
                        ]
                    ),
                }
            ),
        )

    @inlineCallbacks
    def test_compose(self):
        # This test will start with a requested 64 cores.
        # RSD API will not succeed until we are at 8 processors
        # with 8 cores each as seen here:
        # 64 cores / 1 -> 1 CPU with 64 cores
        # 64 cores / 2 -> 2 CPU's with 32 cores
        # 64 cores / 4 -> 4 CPU's with 16 cores each
        # 64 cores / 8 -> 8 CPU's with 8 cores each
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        request = make_requested_machine(cores=64)
        # Set tags to test that the discovered_machine block device's tags
        # will match the requested machine's block_device's tags.
        for idx in range(3):
            request.block_devices[idx].tags = [
                factory.make_name("tag") for _ in range(3)
            ]
        discovered_pod = make_discovered_pod()
        new_machine = make_discovered_machine()
        logical_drives = {
            factory.make_name("lv_path"): factory.make_name("lv_data")
            for _ in range(3)
        }
        targets = {
            factory.make_name("target_path"): factory.make_name("target_data")
            for _ in range(3)
        }
        remote_drives = set(
            [
                factory.make_name("target_path").encode("utf-8")
                for _ in range(3)
            ]
        )
        mock_scrape_logical_drives_and_targets = self.patch(
            driver, "scrape_logical_drives_and_targets"
        )
        mock_scrape_logical_drives_and_targets.return_value = (
            logical_drives,
            targets,
        )
        mock_scrape_remote_drives = self.patch(driver, "scrape_remote_drives")
        mock_scrape_remote_drives.return_value = remote_drives
        mock_get_pod_machine = self.patch(driver, "get_pod_machine")
        mock_get_pod_machine.return_value = new_machine
        mock_convert_request_to_json_payload = self.patch(
            driver, "convert_request_to_json_payload"
        )
        payload = json.dumps({"Test": "Testing Compose"}).encode("utf-8")
        mock_convert_request_to_json_payload.side_effect = [payload] * 4
        mock_redfish_request = self.patch(driver, "redfish_request")
        node_path = b"redfish/v1/Nodes/%s" % new_machine.power_parameters.get(
            "node_id"
        ).encode("utf-8")
        response_headers = Headers({b"location": [join(url, node_path)]})
        mock_redfish_request.side_effect = [
            PartialDownloadError(
                code=HTTPStatus.CONFLICT,
                response=json.dumps(SAMPLE_JSON_PARTIAL_DOWNLOAD_ERROR).encode(
                    "utf-8"
                ),
            )
        ] * 3 + [(None, response_headers)]
        mock_assemble_node = self.patch(driver, "assemble_node")
        mock_set_pxe_boot = self.patch(driver, "set_pxe_boot")
        mock_get_pod_resources = self.patch(driver, "get_pod_resources")
        mock_get_pod_resources.return_value = discovered_pod

        discovered_machine, discovered_pod_hints = yield driver.compose(
            factory.make_name("system_id"), context, request
        )
        self.assertThat(
            mock_convert_request_to_json_payload,
            MockCallsMatch(
                call(1, 32, request, remote_drives, logical_drives, targets),
                call(2, 16, request, remote_drives, logical_drives, targets),
                call(4, 8, request, remote_drives, logical_drives, targets),
                call(8, 4, request, remote_drives, logical_drives, targets),
            ),
        )
        self.assertThat(
            mock_assemble_node,
            MockCalledOnceWith(
                url,
                new_machine.power_parameters.get("node_id").encode("utf-8"),
                headers,
            ),
        )
        self.assertThat(
            mock_set_pxe_boot,
            MockCalledOnceWith(
                url,
                new_machine.power_parameters.get("node_id").encode("utf-8"),
                headers,
            ),
        )
        self.assertThat(
            mock_scrape_logical_drives_and_targets,
            MockCallsMatch(call(url, headers), call(url, headers)),
        )
        self.assertThat(
            mock_scrape_remote_drives,
            MockCallsMatch(call(url, headers), call(url, headers)),
        )
        self.assertThat(
            mock_get_pod_machine,
            MockCalledOnceWith(
                node_path,
                url,
                headers,
                remote_drives,
                logical_drives,
                targets,
                request,
            ),
        )
        self.assertEqual(new_machine, discovered_machine)
        self.assertEqual(discovered_pod.hints, discovered_pod_hints)

    @inlineCallbacks
    def test_compose_raises_error_for_unknown_exception(self):
        driver = RSDPodDriver()
        context = make_context()
        request = make_requested_machine(cores=1)
        discovered_pod = make_discovered_pod()
        new_machines = deepcopy(discovered_pod.machines)
        machines = deepcopy(new_machines)
        mock_scrape_logical_drives_and_targets = self.patch(
            driver, "scrape_logical_drives_and_targets"
        )
        mock_scrape_logical_drives_and_targets.return_value = (None, None)
        mock_scrape_remote_drives = self.patch(driver, "scrape_remote_drives")
        mock_scrape_remote_drives.return_value = None
        mock_get_pod_machines = self.patch(driver, "get_pod_machines")
        mock_get_pod_machines.side_effect = [machines, new_machines]
        mock_convert_request_to_json_payload = self.patch(
            driver, "convert_request_to_json_payload"
        )
        payload = json.dumps({"Test": "Testing Compose"}).encode("utf-8")
        mock_convert_request_to_json_payload.return_value = payload
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.side_effect = Exception("Error")
        with ExpectedException(PodActionError):
            yield driver.compose(
                factory.make_name("system_id"), context, request
            )

    @inlineCallbacks
    def test_compose_raises_error_for_no_allocation(self):
        driver = RSDPodDriver()
        context = make_context()
        request = make_requested_machine(cores=1)
        discovered_pod = make_discovered_pod()
        new_machines = deepcopy(discovered_pod.machines)
        machines = deepcopy(new_machines)
        mock_scrape_logical_drives_and_targets = self.patch(
            driver, "scrape_logical_drives_and_targets"
        )
        mock_scrape_logical_drives_and_targets.return_value = (None, None)
        mock_scrape_remote_drives = self.patch(driver, "scrape_remote_drives")
        mock_scrape_remote_drives.return_value = None
        mock_get_pod_machines = self.patch(driver, "get_pod_machines")
        mock_get_pod_machines.side_effect = [machines, new_machines]
        mock_convert_request_to_json_payload = self.patch(
            driver, "convert_request_to_json_payload"
        )
        payload = json.dumps({"Test": "Testing Compose"}).encode("utf-8")
        mock_convert_request_to_json_payload.side_effect = [payload] * 4
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (None, None)
        with ExpectedException(PodInvalidResources):
            yield driver.compose(
                factory.make_name("system_id"), context, request
            )

    @inlineCallbacks
    def test_delete_node(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, "redfish_request")

        yield driver.delete_node(url, node_id, headers)
        self.assertThat(
            mock_redfish_request,
            MockCalledOnceWith(b"DELETE", join(url, endpoint), headers),
        )

    @inlineCallbacks
    def test_delete_node_continues_on_404_error(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, "redfish_request")
        error = PartialDownloadError(
            response=json.dumps(SAMPLE_JSON_SYSTEMS).encode("utf-8"),
            code=HTTPStatus.NOT_FOUND,
        )
        mock_redfish_request.side_effect = error

        yield driver.delete_node(url, node_id, headers)
        self.assertThat(
            mock_redfish_request,
            MockCalledOnceWith(b"DELETE", join(url, endpoint), headers),
        )

    @inlineCallbacks
    def test_delete_node_raises_when_not_404_error(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, "redfish_request")
        error = PartialDownloadError(
            response=json.dumps(SAMPLE_JSON_SYSTEMS).encode("utf-8"),
            code=HTTPStatus.BAD_REQUEST,
        )
        mock_redfish_request.side_effect = error

        with ExpectedException(PartialDownloadError):
            yield driver.delete_node(url, node_id, headers)
        self.assertThat(
            mock_redfish_request,
            MockCalledOnceWith(b"DELETE", join(url, endpoint), headers),
        )

    @inlineCallbacks
    def test_decompose(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_delete_node = self.patch(driver, "delete_node")
        mock_get_pod_resources = self.patch(driver, "get_pod_resources")
        discovered_pod = make_discovered_pod()
        mock_get_pod_resources.return_value = discovered_pod
        mock_get_pod_hints = self.patch(driver, "get_pod_hints")

        yield driver.decompose(factory.make_name("system_id"), context)
        self.assertThat(
            mock_delete_node, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(
            mock_get_pod_resources, MockCalledOnceWith(url, headers)
        )
        self.assertThat(mock_get_pod_hints, MockCalledOnceWith(discovered_pod))

    @inlineCallbacks
    def test_get_composed_node_state(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_NODE, None)
        uri = join(url, b"redfish/v1/Nodes/%s" % node_id)

        power_state = yield driver.get_composed_node_state(
            url, node_id, headers
        )
        self.assertEqual(power_state, "PoweredOff")
        self.assertThat(
            mock_redfish_request, MockCalledOnceWith(b"GET", uri, headers)
        )

    @inlineCallbacks
    def test_assemble_node_does_not_assemble_if_already_assembled(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.return_value = random.choice(
            ["PoweredOn", "PoweredOff"]
        )

        yield driver.assemble_node(url, node_id, headers)
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers),
        )

    @inlineCallbacks
    def test_assemble_node_assembles_if_not_assembled(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.side_effect = [
            "Allocated",
            "Assembling",
            "Assembled",
        ]
        mock_redfish_request = self.patch(driver, "redfish_request")
        endpoint = (
            b"redfish/v1/Nodes/%s/Actions/ComposedNode.Assemble" % node_id
        )
        uri = join(url, endpoint)

        yield driver.assemble_node(url, node_id, headers)
        self.assertThat(
            mock_get_composed_node_state,
            MockCallsMatch(
                call(url, node_id, headers),
                call(url, node_id, headers),
                call(url, node_id, headers),
            ),
        )
        self.assertThat(
            mock_redfish_request, MockCalledOnceWith(b"POST", uri, headers)
        )

    @inlineCallbacks
    def test_assemble_node_raises_error_if_original_power_state_failed(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.return_value = "Failed"
        mock_delete_node = self.patch(driver, "delete_node")
        mock_redfish_request = self.patch(driver, "redfish_request")

        with ExpectedException(PodFatalError):
            yield driver.assemble_node(url, node_id, headers)
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers),
        )
        self.assertThat(
            mock_delete_node, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(mock_redfish_request, MockNotCalled())

    @inlineCallbacks
    def test_assemble_node_raises_error_if_assembling_fails(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.side_effect = [
            "Allocated",
            "Assembling",
            "Failed",
        ]
        mock_delete_node = self.patch(driver, "delete_node")
        mock_redfish_request = self.patch(driver, "redfish_request")
        endpoint = (
            b"redfish/v1/Nodes/%s/Actions/ComposedNode.Assemble" % node_id
        )
        uri = join(url, endpoint)

        with ExpectedException(PodFatalError):
            yield driver.assemble_node(url, node_id, headers)
        self.assertThat(
            mock_get_composed_node_state,
            MockCallsMatch(
                call(url, node_id, headers),
                call(url, node_id, headers),
                call(url, node_id, headers),
            ),
        )
        self.assertThat(
            mock_redfish_request, MockCalledOnceWith(b"POST", uri, headers)
        )
        self.assertThat(
            mock_delete_node, MockCalledOnceWith(url, node_id, headers)
        )

    @inlineCallbacks
    def test_set_pxe_boot(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_file_body_producer = self.patch(rsd_module, "FileBodyProducer")
        payload = FileBodyProducer(
            BytesIO(
                json.dumps(
                    {
                        "Boot": {
                            "BootSourceOverrideEnabled": "Once",
                            "BootSourceOverrideTarget": "Pxe",
                        }
                    }
                ).encode("utf-8")
            )
        )
        mock_file_body_producer.return_value = payload
        mock_redfish_request = self.patch(driver, "redfish_request")

        yield driver.set_pxe_boot(url, node_id, headers)
        self.assertThat(
            mock_redfish_request,
            MockCalledOnceWith(
                b"PATCH",
                join(url, b"redfish/v1/Nodes/%s" % node_id),
                headers,
                payload,
            ),
        )

    @inlineCallbacks
    def test_power_on(self):
        driver = RSDPodDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_set_pxe_boot = self.patch(driver, "set_pxe_boot")
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "on"
        mock_power = self.patch(driver, "power")

        yield driver.power_on(system_id, context)
        self.assertThat(
            mock_set_pxe_boot, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(
            mock_power_query, MockCalledOnceWith(system_id, context)
        )
        self.assertThat(
            mock_power,
            MockCallsMatch(
                call("ForceOff", url, node_id, headers),
                call("On", url, node_id, headers),
            ),
        )

    @inlineCallbacks
    def test_power_off(self):
        driver = RSDPodDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_set_pxe_boot = self.patch(driver, "set_pxe_boot")
        mock_power = self.patch(driver, "power")

        yield driver.power_off(system_id, context)
        self.assertThat(
            mock_set_pxe_boot, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(
            mock_power, MockCalledOnceWith("ForceOff", url, node_id, headers)
        )

    @inlineCallbacks
    def test_power_query_queries_on(self):
        driver = RSDPodDriver()
        power_change = "PoweredOn"
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_assemble_node = self.patch(driver, "assemble_node")
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.return_value = power_change
        mock_redfish_request = self.patch(driver, "redfish_request")
        NODE_POWERED_ON = deepcopy(SAMPLE_JSON_NODE)
        NODE_POWERED_ON["PowerState"] = "On"
        mock_redfish_request.return_value = (NODE_POWERED_ON, None)

        power_state = yield driver.power_query(system_id, context)
        self.assertThat(
            mock_assemble_node, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers),
        )
        self.assertEqual(power_state, RSD_NODE_POWER_STATE[power_change])

    @inlineCallbacks
    def test_power_query_queries_off(self):
        driver = RSDPodDriver()
        power_change = "PoweredOff"
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_assemble_node = self.patch(driver, "assemble_node")
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.return_value = power_change
        mock_redfish_request = self.patch(driver, "redfish_request")
        mock_redfish_request.return_value = (SAMPLE_JSON_NODE, None)

        power_state = yield driver.power_query(system_id, context)
        self.assertThat(
            mock_assemble_node, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers),
        )
        self.assertEqual(power_state, RSD_NODE_POWER_STATE[power_change])

    @inlineCallbacks
    def test_power_query_raises_error_unknown_power_state(self):
        driver = RSDPodDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = driver.make_auth_headers(**context)
        mock_assemble_node = self.patch(driver, "assemble_node")
        mock_get_composed_node_state = self.patch(
            driver, "get_composed_node_state"
        )
        mock_get_composed_node_state.return_value = "Error"

        with ExpectedException(PodActionError):
            yield driver.power_query(system_id, context)
        self.assertThat(
            mock_assemble_node, MockCalledOnceWith(url, node_id, headers)
        )
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers),
        )
