# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod.rsd`."""

__all__ = []

from base64 import b64encode
from http import HTTPStatus
from io import BytesIO
import json
from os.path import join
import random
from unittest.mock import (
    call,
    Mock,
)

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.drivers.pod import (
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
from provisioningserver.drivers.pod.rsd import (
    RSD_NODE_POWER_STATE,
    RSDPodDriver,
    WebClientContextFactory,
)
import provisioningserver.drivers.pod.rsd as rsd_module
from provisioningserver.rpc.exceptions import PodInvalidResources
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)
from twisted.internet._sslverify import ClientTLSOptions
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.web.client import (
    FileBodyProducer,
    PartialDownloadError,
)
from twisted.web.http_headers import Headers


SAMPLE_JSON_SYSTEMS = {
    "@odata.context": "/redfish/v1/$metadata#Systems",
    "@odata.id": "/redfish/v1/Systems",
    "@odata.type": "#ComputerSystemCollection.ComputerSystemCollection",
    "Name": "Computer System Collection",
    "Description": "Computer System Collection",
    "Members@odata.count": 8,
    "Members": [{
        "@odata.id": "/redfish/v1/Systems/1"
    }, {
        "@odata.id": "/redfish/v1/Systems/2"
    }, {
        "@odata.id": "/redfish/v1/Systems/3"
    }, {
        "@odata.id": "/redfish/v1/Systems/4"
    }, {
        "@odata.id": "/redfish/v1/Systems/5"
    }, {
        "@odata.id": "/redfish/v1/Systems/6"
    }, {
        "@odata.id": "/redfish/v1/Systems/7"
    }, {
        "@odata.id": "/redfish/v1/Systems/8"
    }]
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
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": "OK"
    },
    "IndicatorLED": None,
    "PowerState": "On",
    "Boot": {
        "BootSourceOverrideEnabled": "Disabled",
        "BootSourceOverrideTarget": "None",
        "BootSourceOverrideTarget@Redfish.AllowableValues": ["Hdd", "Pxe"]
    },
    "BiosVersion": "F20A1A05_D",
    "ProcessorSummary": {
        "Count": 2,
        "Model": "Intel(R) Xeon(R) CPU E5-2695 v3 @ 2.30GHz",
        "Status": {
            "State": "Enabled",
            "Health": "OK",
            "HealthRollup": "OK"
        }
    },
    "MemorySummary": {
        "TotalSystemMemoryGiB": 30,
        "Status": {
            "State": "Enabled",
            "Health": "OK",
            "HealthRollup": "OK"
        }
    },
    "Processors": {
        "@odata.id": "/redfish/v1/Systems/1/Processors"
    },
    "EthernetInterfaces": {
        "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces"
    },
    "SimpleStorage": {
        "@odata.id": "/redfish/v1/Systems/1/SimpleStorage"
    },
    "Memory": {
        "@odata.id": "/redfish/v1/Systems/1/Memory"
    },
    "MemoryChunks": {
        "@odata.id": "/redfish/v1/Systems/1/MemoryChunks"
    },
    "Links": {
        "Chassis": [{
            "@odata.id": "/redfish/v1/Chassis/5"
        }],
        "ManagedBy": [{
            "@odata.id": "/redfish/v1/Managers/6"
        }],
        "Oem": {}
    },
    "Actions": {
        "#ComputerSystem.Reset": {
            "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
            "ResetType@Redfish.AllowableValues": [],
        },
        "Oem": {
            "Intel_RackScale": {
                "#ComputerSystem.StartDeepDiscovery": {
                    "target": "",
                }
            }
        }
    },
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.ComputerSystem",
            "Adapters": {
                "@odata.id": "/redfish/v1/Systems/1/Adapters"
            },
            "PciDevices": [{
                "VendorId": "8086",
                "DeviceId": "2fd3"
            }, {
                "VendorId": "8086",
                "DeviceId": "2f6f"
            }],
            "DiscoveryState": "Deep",
            "ProcessorSockets": None,
            "MemorySockets": None
        }
    }
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
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": "OK"
    },
    "Processors": {
        "Count": 2,
        "Model": "Intel(R) Xeon(R) CPU E5-2695 v3 @ 2.30GHz",
        "Status": {
            "State": "Enabled",
            "Health": "OK",
            "HealthRollup": "OK"
        }
    },
    "Memory": {
        "TotalSystemMemoryGiB": 30,
        "Status": {
            "State": "Enabled",
            "Health": "OK",
            "HealthRollup": "OK"
        }
    },
    "ComposedNodeState": "PoweredOff",
    "Boot": {
        "BootSourceOverrideEnabled": "Once",
        "BootSourceOverrideTarget": "Pxe",
        "BootSourceOverrideTarget@Redfish.AllowableValues": ["Hdd", "Pxe"]
    },
    "Oem": {},
    "Links": {
        "ComputerSystem": {
            "@odata.id": "/redfish/v1/Systems/1"
        },
        "Processors": [{
            "@odata.id": "/redfish/v1/Systems/1/Processors/1"
        }, {
            "@odata.id": "/redfish/v1/Systems/1/Processors/2"
        }],
        "Memory": [{
            "@odata.id": "/redfish/v1/Systems/1/Memory/1"
        }, {
            "@odata.id": "/redfish/v1/Systems/1/Memory/2"
        }, {
            "@odata.id": "/redfish/v1/Systems/1/Memory/3"
        }, {
            "@odata.id": "/redfish/v1/Systems/1/Memory/4"
        }],
        "EthernetInterfaces": [{
            "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/4"
        }, {
            "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5"
        }],
        "LocalDrives": [{
            "@odata.id": "/redfish/v1/Systems/1/Adapters/3/Devices/2"
        }],
        "RemoteDrives": [],
        "ManagedBy": [{
            "@odata.id": "/redfish/v1/Managers/1"
        }],
        "Oem": {}
    },
    "Actions": {
        "#ComposedNode.Reset": {
            "target": "/redfish/v1/Nodes/1/Actions/ComposedNode.Reset",
            "ResetType@DMTF.AllowableValues": [],
        },
        "#ComposedNode.Assemble": {
            "target": "/redfish/v1/Nodes/1/Actions/ComposedNode.Assemble"
        }
    }
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
        "MicrocodeInfo": "0x2d"
    },
    "MaxSpeedMHz": 2300,
    "TotalCores": 14,
    "TotalThreads": 28,
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": None
    },
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.Processor",
            "Brand": "E5",
            "ContainedBy": {
                "@odata.id": "/redfish/v1/Systems/1"
            }
        }
    }
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
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": None
    },
    "Oem": {},
    "Links": {
        "ContainedBy": {
            "@odata.id": "/redfish/v1/Systems/1/Adapters/3"
        },
        "Oem": {}
    }
}


SAMPLE_JSON_INTERFACE = {
    "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5",
    "@odata.type": "#EthernetInterface.1.0.0.EthernetInterface",
    "Id": "5",
    "Name": "Ethernet Interface",
    "Description": "Ethernet Interface description",
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": None
    },
    "InterfaceEnabled": True,
    "PermanentMACAddress": "54:ab:3a:36:af:45",
    "MACAddress": "54:ab:3a:36:af:45",
    "SpeedMbps": None,
    "AutoNeg": None,
    "FullDuplex": None,
    "MTUSize": None,
    "HostName": None,
    "FQDN": None,
    "VLANs": {
        "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5/VLANs"
    },
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
                }
            }
        }
    }
}


SAMPLE_JSON_PORT = {
    "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2",
    "@odata.type": "#EthernetSwitchPort.1.0.0.EthernetSwitchPort",
    "Id": "2",
    "Name": "Port29",
    "Description": "Ethernet Switch Port description",
    "PortId": "sw0p41",
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": "OK"
    },
    "LinkType": "PCIe",
    "OperationalState": "Up",
    "AdministrativeState": "Up",
    "LinkSpeedMbps": 40000,
    "NeighborInfo": {
        "CableId": None,
        "PortId": None,
        "SwitchId": None
    },
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
    "VLANs": {
        "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2/VLANs"
    },
    "Links": {
        "PrimaryVLAN": {
            "@odata.id": "/redfish/v1/EthernetSwitches/1/Ports/2/VLANs/9"
        },
        "Switch": {
            "@odata.id": "/redfish/v1/EthernetSwitches/1"
        },
        "MemberOfPort": None,
        "PortMembers": [],
        "Oem": {
            "Intel_RackScale": {
                "@odata.type": "#Intel.Oem.EthernetSwitchPort",
                "NeighborInterface": {
                    "@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/5"
                }
            }
        }
    }
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
                "HealthRollup": None
            }
        }
    }
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
    "Status": {
        "State": "Enabled",
        "Health": "OK",
        "HealthRollup": None
    },
    "OperatingSpeedMhz": 2133,
    "Regions": [{
        "RegionId": "0",
        "MemoryClassification": None,
        "OffsetMiB": 0,
        "SizeMiB": 7812
    }],
    "OperatingMemoryModes": [],
    "Oem": {
        "Intel_RackScale": {
            "@odata.type": "#Intel.Oem.Memory",
            "VoltageVolt": 1.2
        }
    }
}


def make_context():
    return {
        'power_address': factory.make_ip_address(),
        'power_user': factory.make_name('power_user'),
        'power_pass': factory.make_name('power_pass'),
        'node_id': factory.make_name('node_id'),
    }


def make_requested_machine(cores=None, memory=None, cpu_speed=None):
    if cores is None:
        cores = random.randint(2, 4)
    if memory is None:
        memory = random.randint(1024, 4096)
    if cpu_speed is None:
        cpu_speed = random.randint(2000, 3000)
    block_devices = [
        RequestedMachineBlockDevice(
            size=random.randint(1024 ** 3, 4 * 1024 ** 3))
        for _ in range(3)
    ]
    interfaces = [
        RequestedMachineInterface()
        for _ in range(3)
    ]
    return RequestedMachine(
        architecture="amd64/generic",
        cores=cores, memory=memory, cpu_speed=cpu_speed,
        block_devices=block_devices, interfaces=interfaces)


def make_discovered_machine():
    block_devices = [
        DiscoveredMachineBlockDevice(
            model=factory.make_name("model"),
            serial=factory.make_name("serial"),
            size=random.randint(1024 ** 3, 4 * 1024 ** 3))
        for _ in range(3)
    ]
    interfaces = [
        DiscoveredMachineInterface(
            mac_address=factory.make_mac_address())
        for _ in range(3)
    ]
    return DiscoveredMachine(
        architecture="amd64/generic", cores=random.randint(2, 4),
        cpu_speed=random.randint(2000, 3000),
        memory=random.randint(1024, 4096),
        interfaces=interfaces, block_devices=block_devices,
        power_state=factory.make_name('unknown'), power_parameters={
            'node_id': factory.make_name('node_id')})


def make_discovered_pod(
        cores=None, cpu_speed=None, memory=None, storage=None, disks=None):
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
        cores=cores, cpu_speed=cpu_speed, memory=memory,
        local_storage=storage, hints=DiscoveredPodHints(
            cores=0, cpu_speed=0, memory=0,
            local_storage=0, local_disks=0),
        machines=machines, local_disks=disks)
    # Add cpu_speeds to the DiscoveredPod.
    discovered_pod.cpu_speeds = cpu_speeds
    return discovered_pod


class TestWebClientContextFactory(MAASTestCase):

    def test_creatorForNetloc_returns_tls_options(self):
        hostname = factory.make_name('hostname').encode('utf-8')
        port = random.randint(1000, 2000)
        contextFactory = WebClientContextFactory()
        opts = contextFactory.creatorForNetloc(hostname, port)
        self.assertIsInstance(opts, ClientTLSOptions)


class TestRSDPodDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = RSDPodDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test_get_url_with_ip(self):
        driver = RSDPodDriver()
        context = make_context()
        ip = context.get('power_address').encode('utf-8')
        expected_url = b"https://%s" % ip
        url = driver.get_url(context)
        self.assertEqual(expected_url, url)

    def test_get_url_with_https(self):
        driver = RSDPodDriver()
        context = make_context()
        context['power_address'] = join(
            "https://", context['power_address'])
        expected_url = context.get('power_address').encode('utf-8')
        url = driver.get_url(context)
        self.assertEqual(expected_url, url)

    def test_get_url_with_http(self):
        driver = RSDPodDriver()
        context = make_context()
        context['power_address'] = join(
            "http://", context['power_address'])
        expected_url = context.get('power_address').encode('utf-8')
        url = driver.get_url(context)
        self.assertEqual(expected_url, url)

    def test__make_auth_headers(self):
        power_user = factory.make_name('power_user')
        power_pass = factory.make_name('power_pass')
        creds = "%s:%s" % (power_user, power_pass)
        authorization = b64encode(creds.encode('utf-8'))
        attributes = {
            b"User-Agent": [b"MAAS"],
            b"Authorization": [b"Basic " + authorization],
            b"Content-Type": [b"application/json; charset=utf-8"],
            }
        driver = RSDPodDriver()
        headers = driver.make_auth_headers(power_user, power_pass)
        self.assertEquals(headers, Headers(attributes))

    @inlineCallbacks
    def test_redfish_request_renders_response(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        uri = join(url, b"redfish/v1/Systems")
        headers = driver.make_auth_headers(**context)
        mock_agent = self.patch(rsd_module, 'Agent')
        mock_agent.return_value.request = Mock()
        mock_agent.return_value.request.return_value = succeed(None)
        mock_readBody = self.patch(rsd_module, 'readBody')
        mock_readBody.return_value = succeed(
            json.dumps(SAMPLE_JSON_SYSTEMS).encode('utf-8'))
        expected_response = SAMPLE_JSON_SYSTEMS

        response = yield driver.redfish_request(b"GET", uri, headers)
        self.assertEquals(expected_response, response)

    @inlineCallbacks
    def test_redfish_request_continues_partial_download_error(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        uri = join(url, b"redfish/v1/Systems")
        headers = driver.make_auth_headers(**context)
        mock_agent = self.patch(rsd_module, 'Agent')
        mock_agent.return_value.request = Mock()
        mock_agent.return_value.request.return_value = succeed(None)
        mock_readBody = self.patch(rsd_module, 'readBody')
        error = PartialDownloadError(
            response=json.dumps(SAMPLE_JSON_SYSTEMS).encode('utf-8'),
            code=HTTPStatus.OK)
        mock_readBody.return_value = fail(error)
        expected_response = SAMPLE_JSON_SYSTEMS

        response = yield driver.redfish_request(b"GET", uri, headers)
        self.assertEquals(expected_response, response)

    @inlineCallbacks
    def test_redfish_request_raises_failures(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        uri = join(url, b"redfish/v1/Systems")
        headers = driver.make_auth_headers(**context)
        mock_agent = self.patch(rsd_module, 'Agent')
        mock_agent.return_value.request = Mock()
        mock_agent.return_value.request.return_value = succeed("Response")
        mock_readBody = self.patch(rsd_module, 'readBody')
        error = PartialDownloadError(
            response=json.dumps(SAMPLE_JSON_SYSTEMS).encode('utf-8'),
            code=HTTPStatus.NOT_FOUND)
        mock_readBody.return_value = fail(error)

        with ExpectedException(PartialDownloadError):
            yield driver.redfish_request(b"GET", uri, headers)
            self.assertThat(mock_readBody, MockCalledOnceWith(
                "Response"))

    @inlineCallbacks
    def test__list_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        endpoint = factory.make_name('endpoint')
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.return_value = SAMPLE_JSON_SYSTEMS
        expected_data = SAMPLE_JSON_SYSTEMS
        members = expected_data.get('Members')
        resource_ids = []
        for resource in members:
            resource_ids.append(
                resource['@odata.id'].lstrip('/').encode('utf-8'))
        resources = yield driver.list_resources(endpoint, headers)
        self.assertItemsEqual(resources, resource_ids)

    @inlineCallbacks
    def test__get_pod_memory_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.return_value = [
            b"redfish/v1/Systems/1/Memory/1",
            b"redfish/v1/Systems/1/Memory/2",
        ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_MEMORY,
            SAMPLE_JSON_MEMORY,
        ]

        memories = yield driver.get_pod_memory_resources(
            url, headers, system)
        self.assertEquals([7812, 7812], memories)

    @inlineCallbacks
    def test__get_pod_processor_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.return_value = [
            b"redfish/v1/Systems/1/Processors/1",
            b"redfish/v1/Systems/1/Processors/2",
        ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_PROCESSOR,
            SAMPLE_JSON_PROCESSOR,
        ]

        cores, cpu_speeds, arch = yield driver.get_pod_processor_resources(
            url, headers, system)
        self.assertEquals([28, 28], cores)
        self.assertEquals([2300, 2300], cpu_speeds)
        self.assertEquals("x86-64", arch)

    @inlineCallbacks
    def test__get_pod_storage_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.side_effect = [
            [b"redfish/v1/Systems/1/Adapters/3"],
            [
                b"redfish/v1/Systems/1/Adapters/3/Devices/2",
                b"redfish/v1/Systems/1/Adapters/3/Devices/3",
            ],
        ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_DEVICE,
            SAMPLE_JSON_DEVICE,
        ]

        storages = yield driver.get_pod_storage_resources(
            url, headers, system)
        self.assertEquals(
            [111.7587089538574, 111.7587089538574], storages)

    @inlineCallbacks
    def test__scan_machine_memories(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        machine = DiscoveredMachine(
            architecture="amd64/generic", cores=0, cpu_speed=0,
            memory=0, interfaces=[], block_devices=[],
            power_state="unknown",
            power_parameters={})
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.return_value = [
            b"redfish/v1/Systems/1/Memory/1"
        ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.return_value = SAMPLE_JSON_MEMORY

        yield driver.scan_machine_memories(url, headers, system, machine)
        self.assertEquals(7812, machine.memory)

    @inlineCallbacks
    def test__scan_machine_processors(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        machine = DiscoveredMachine(
            architecture="amd64/generic", cores=0, cpu_speed=0,
            memory=0, interfaces=[], block_devices=[],
            power_state="unknown",
            power_parameters={})
        machine.cpu_speeds = []
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.return_value = [
            b"redfish/v1/Systems/1/Processors/1"
        ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.return_value = SAMPLE_JSON_PROCESSOR

        yield driver.scan_machine_processors(url, headers, system, machine)
        self.assertEquals(28, machine.cores)
        self.assertEquals([2300], machine.cpu_speeds)
        self.assertEquals("amd64/generic", machine.architecture)

    @inlineCallbacks
    def test__scan_machine_local_storage(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        device = b"redfish/v1/Systems/1/Adapters/3/Devices/%s"
        machine = DiscoveredMachine(
            architecture="amd64/generic", cores=0, cpu_speed=0,
            memory=0, interfaces=[], block_devices=[],
            power_state="unknown",
            power_parameters={})
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.side_effect = [
            [b"redfish/v1/Systems/1/Adapters/3"],
            [device % b"2", device % b"3"],
        ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_DEVICE,
            SAMPLE_JSON_DEVICE,
        ]

        yield driver.scan_machine_local_storage(
            url, headers, system, machine)
        for block_device in machine.block_devices:
            self.assertEquals("INTEL_SSDMCEAC120B3", block_device.model)
            self.assertEquals("CVLI310601PY120E", block_device.serial)
            self.assertEquals(119999999999.99997, block_device.size)
            self.assertEquals(['ssd'], block_device.tags)
        self.assertThat(mock_redfish_request, MockCallsMatch(
            call(b"GET", join(url, device % b"2"), headers),
            call(b"GET", join(url, device % b"3"), headers)))

    @inlineCallbacks
    def test__scan_machine_interfaces(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        system = b"redfish/v1/Systems/1"
        interface = b"redfish/v1/Systems/1/EthernetInterfaces/%s"
        machine = DiscoveredMachine(
            architecture="amd64/generic", cores=0, cpu_speed=0,
            memory=0, interfaces=[], block_devices=[],
            power_state="unknown",
            power_parameters={})
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.return_value = [
            interface % b"4", interface % b"5", interface % b"6"]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        nic1_data = SAMPLE_JSON_INTERFACE.copy()
        nic1_data['SpeedMbps'] = 900
        nic2_data = SAMPLE_JSON_INTERFACE.copy()
        nic2_data['SpeedMbps'] = 1000
        nic3_data = SAMPLE_JSON_INTERFACE.copy()
        nic3_data['SpeedMbps'] = 2000
        mock_redfish_request.side_effect = [
            nic1_data,
            SAMPLE_JSON_PORT,
            SAMPLE_JSON_VLAN,
            nic2_data,
            SAMPLE_JSON_PORT,
            SAMPLE_JSON_VLAN,
            nic3_data,
            SAMPLE_JSON_PORT,
            SAMPLE_JSON_VLAN,
        ]

        yield driver.scan_machine_interfaces(
            url, headers, system, machine)
        self.assertThat(machine.interfaces, MatchesListwise([
            MatchesStructure(
                mac_address=Equals('54:ab:3a:36:af:45'),
                vid=Equals(4088),
                tags=Equals(['e900']),
            ),
            MatchesStructure(
                mac_address=Equals('54:ab:3a:36:af:45'),
                vid=Equals(4088),
                tags=Equals(['1.0']),
            ),
            MatchesStructure(
                mac_address=Equals('54:ab:3a:36:af:45'),
                vid=Equals(4088),
                tags=Equals(['2.0']),
            ),
        ]))

    @inlineCallbacks
    def test__get_pod_resources(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        mock_list_resources = self.patch(driver, 'list_resources')
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
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_MEMORY,
            SAMPLE_JSON_PROCESSOR,
            SAMPLE_JSON_DEVICE,
            SAMPLE_JSON_MEMORY,
            SAMPLE_JSON_PROCESSOR,
            SAMPLE_JSON_DEVICE,
            ]

        pod = yield driver.get_pod_resources(url, headers)
        self.assertEquals(["amd64/generic"], pod.architectures)
        self.assertEquals(28 * 2, pod.cores)
        self.assertEquals(2300, pod.cpu_speed)
        self.assertEquals(7812 * 2, pod.memory)
        self.assertEquals(119999999999.99997 * 2, pod.local_storage)
        self.assertEquals(
            [Capabilities.COMPOSABLE, Capabilities.FIXED_LOCAL_STORAGE],
            pod.capabilities)

    @inlineCallbacks
    def test_get_pod_resources_skips_invalid_systems(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.side_effect = [
            [b"redfish/v1/Systems/1"],
            [b"redfish/v1/Systems/1/Processors/1"],
            [b"redfish/v1/Systems/1/Adapters/3"],
            [b"redfish/v1/Systems/1/Adapters/3/Devices/2"],
            ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_get_pod_memory_resources = self.patch(
            driver, 'get_pod_memory_resources')
        mock_get_pod_memory_resources.return_value = [None]
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_SYSTEM,
            SAMPLE_JSON_PROCESSOR,
            SAMPLE_JSON_DEVICE,
            ]

        pod = yield driver.get_pod_resources(url, headers)
        self.assertEquals(0, pod.cores)
        self.assertEquals(0, pod.cpu_speed)
        self.assertEquals(0, pod.memory)
        self.assertEquals(0, pod.local_storage)

    @inlineCallbacks
    def test__get_pod_machines(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        headers = driver.make_auth_headers(**context)
        mock_list_resources = self.patch(driver, 'list_resources')
        mock_list_resources.side_effect = [
            [b"redfish/v1/Nodes/1"],
            [b"redfish/v1/Systems/1/Memory/1"],
            [b"redfish/v1/Systems/1/Processors/1"],
            [b"redfish/v1/Systems/1/Adapters/3"],
            [b"redfish/v1/Systems/1/Adapters/3/Devices/2"],
            [b"redfish/v1/Systems/1/EthernetInterfaces/5"],
            ]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [
            SAMPLE_JSON_NODE,
            SAMPLE_JSON_MEMORY,
            SAMPLE_JSON_PROCESSOR,
            SAMPLE_JSON_DEVICE,
            SAMPLE_JSON_INTERFACE,
            SAMPLE_JSON_PORT,
            SAMPLE_JSON_VLAN
            ]

        discovered_machines = yield driver.get_pod_machines(url, headers)
        machine = discovered_machines[0]
        self.assertEquals(1, len(discovered_machines))
        self.assertEquals("amd64/generic", machine.architecture)
        self.assertEquals(28, machine.cores)
        self.assertEquals(2300, machine.cpu_speed)
        self.assertEquals(7812, machine.memory)
        self.assertEquals(
            "54:ab:3a:36:af:45", machine.interfaces[0].mac_address)
        self.assertEquals(
            "INTEL_SSDMCEAC120B3", machine.block_devices[0].model)
        self.assertEquals("CVLI310601PY120E", machine.block_devices[0].serial)
        self.assertEquals(119999999999.99997, machine.block_devices[0].size)
        self.assertEquals(['ssd'], machine.block_devices[0].tags)
        self.assertEquals("off", machine.power_state)
        self.assertEquals({'node_id': '1'}, machine.power_parameters)

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
        expected_local_storage = (
            discovered_pod.local_storage - used_storage)
        expected_local_disks = (
            discovered_pod.local_disks - used_disks)

        discovered_pod_hints = driver.get_pod_hints(discovered_pod)
        self.assertEquals(
            expected_cpu_speed, discovered_pod_hints.cpu_speed)
        self.assertEquals(expected_cores, discovered_pod_hints.cores)
        self.assertEquals(expected_memory, discovered_pod_hints.memory)
        self.assertEquals(
            expected_local_storage, discovered_pod_hints.local_storage)
        self.assertEquals(
            expected_local_disks, discovered_pod_hints.local_disks)

    @inlineCallbacks
    def test_discover(self):
        driver = RSDPodDriver()
        context = make_context()
        headers = driver.make_auth_headers(**context)
        url = driver.get_url(context)
        mock_get_pod_resources = self.patch(
            driver, 'get_pod_resources')
        mock_get_pod_machines = self.patch(driver, 'get_pod_machines')
        mock_get_pod_hints = self.patch(driver, 'get_pod_hints')

        yield driver.discover(factory.make_name('system_id'), context)
        self.assertThat(
            mock_get_pod_resources, MockCalledOnceWith(url, headers))
        self.assertThat(
            mock_get_pod_machines, MockCalledOnceWith(url, headers))
        self.assertThat(mock_get_pod_hints, MockCalledOnceWith(
            mock_get_pod_resources.return_value))

    def test__convert_request_to_json_payload(self):
        driver = RSDPodDriver()
        request = make_requested_machine()
        processors = 2
        cores = request.cores / 2
        payload = driver.convert_request_to_json_payload(
            processors, cores, request)
        self.assertThat(
            json.loads(payload.decode('utf-8')),
            MatchesDict({
                "Processors": MatchesListwise([
                    MatchesDict({
                        "Model": Equals(None),
                        "TotalCores": Equals(cores),
                        "AchievableSpeedMHz": Equals(request.cpu_speed),
                        "InstructionSet": Equals("x86-64"),
                    }),
                    MatchesDict({
                        "Model": Equals(None),
                        "TotalCores": Equals(cores),
                        "AchievableSpeedMHz": Equals(request.cpu_speed),
                        "InstructionSet": Equals("x86-64"),
                    })]),
                "Memory": MatchesListwise([
                    MatchesDict({
                        "SpeedMHz": Equals(None),
                        "CapacityMiB": Equals(request.memory),
                        "DataWidthBits": Equals(None)
                    })]),
                "EthernetInterfaces": MatchesListwise([
                    MatchesDict({
                        "SpeedMbps": Equals(None),
                        "PrimaryVLAN": Equals(None)
                    }),
                    MatchesDict({
                        "SpeedMbps": Equals(None),
                        "PrimaryVLAN": Equals(None)
                    }),
                    MatchesDict({
                        "SpeedMbps": Equals(None),
                        "PrimaryVLAN": Equals(None)
                    })]),
                "LocalDrives": MatchesListwise([
                    MatchesDict({
                        "SerialNumber": Equals(None),
                        "Type": Equals(None),
                        "CapacityGiB": Equals(
                            request.block_devices[0].size / 1073741824),
                        "MinRPM": Equals(None),
                        "Interface": Equals(None)
                    }),
                    MatchesDict({
                        "SerialNumber": Equals(None),
                        "Type": Equals(None),
                        "CapacityGiB": Equals(
                            request.block_devices[1].size / 1073741824),
                        "MinRPM": Equals(None),
                        "Interface": Equals(None)
                    }),
                    MatchesDict({
                        "SerialNumber": Equals(None),
                        "Type": Equals(None),
                        "CapacityGiB": Equals(
                            request.block_devices[2].size / 1073741824),
                        "MinRPM": Equals(None),
                        "Interface": Equals(None)
                    })
                ])
            }))

    @inlineCallbacks
    def test__compose(self):
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
        discovered_pod = make_discovered_pod()
        new_machines = discovered_pod.machines.copy()
        machines = new_machines.copy()
        new_machine = machines.pop(0)
        mock_get_pod_machines = self.patch(driver, 'get_pod_machines')
        mock_get_pod_machines.side_effect = [
            machines, new_machines]
        mock_convert_request_to_json_payload = self.patch(
            driver, 'convert_request_to_json_payload')
        payload = json.dumps(
            {
                'Test': "Testing Compose"
            }).encode('utf-8')
        mock_convert_request_to_json_payload.side_effect = [payload] * 4
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [Exception('Error')] * 3 + [None]
        mock_assemble_node = self.patch(driver, 'assemble_node')
        mock_set_pxe_boot = self.patch(driver, 'set_pxe_boot')
        mock_get_pod_resources = self.patch(driver, 'get_pod_resources')
        mock_get_pod_resources.return_value = discovered_pod

        discovered_machine, discovered_pod_hints = yield driver.compose(
            factory.make_name('system_id'), context, request)
        self.assertThat(
            mock_convert_request_to_json_payload, MockCallsMatch(
                call(1, 32, request), call(2, 16, request),
                call(4, 8, request), call(8, 4, request)))
        self.assertThat(mock_assemble_node, MockCalledOnceWith(
            url, new_machine.power_parameters.get(
                'node_id').encode('utf-8'), headers))
        self.assertThat(mock_set_pxe_boot, MockCalledOnceWith(
            url, new_machine.power_parameters.get(
                'node_id').encode('utf-8'), headers))
        self.assertEquals(new_machine, discovered_machine)
        self.assertEquals(discovered_pod.hints, discovered_pod_hints)

    @inlineCallbacks
    def test_compose_raises_error_for_no_allocation(self):
        driver = RSDPodDriver()
        context = make_context()
        request = make_requested_machine(cores=1)
        discovered_pod = make_discovered_pod()
        new_machines = discovered_pod.machines.copy()
        machines = new_machines.copy()
        mock_get_pod_machines = self.patch(driver, 'get_pod_machines')
        mock_get_pod_machines.side_effect = [
            machines, new_machines]
        mock_convert_request_to_json_payload = self.patch(
            driver, 'convert_request_to_json_payload')
        payload = json.dumps(
            {
                'Test': "Testing Compose"
            }).encode('utf-8')
        mock_convert_request_to_json_payload.side_effect = [payload] * 4
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.side_effect = [Exception('Error')]
        with ExpectedException(PodInvalidResources):
            yield driver.compose(
                factory.make_name('system_id'), context, request)

    @inlineCallbacks
    def test__decompose(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_get_pod_resources = self.patch(driver, 'get_pod_resources')
        discovered_pod = make_discovered_pod()
        mock_get_pod_resources.return_value = discovered_pod
        mock_get_pod_hints = self.patch(driver, 'get_pod_hints')

        yield driver.decompose(
            factory.make_name('system_id'), context)
        self.assertThat(mock_redfish_request, MockCalledOnceWith(
            b"DELETE", join(url, endpoint), headers))
        self.assertThat(mock_get_pod_resources, MockCalledOnceWith(
            url, headers))
        self.assertThat(mock_get_pod_hints, MockCalledOnceWith(
            discovered_pod))

    @inlineCallbacks
    def test_decompose_continues_on_404_error(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        mock_redfish_request = self.patch(driver, 'redfish_request')
        error = PartialDownloadError(
            response=json.dumps(SAMPLE_JSON_SYSTEMS).encode('utf-8'),
            code=HTTPStatus.NOT_FOUND)
        mock_redfish_request.side_effect = error
        mock_get_pod_resources = self.patch(driver, 'get_pod_resources')
        discovered_pod = make_discovered_pod()
        mock_get_pod_resources.return_value = discovered_pod
        mock_get_pod_hints = self.patch(driver, 'get_pod_hints')

        yield driver.decompose(
            factory.make_name('system_id'), context)
        self.assertThat(mock_redfish_request, MockCalledOnceWith(
            b"DELETE", join(url, endpoint), headers))
        self.assertThat(mock_get_pod_resources, MockCalledOnceWith(
            url, headers))
        self.assertThat(mock_get_pod_hints, MockCalledOnceWith(
            discovered_pod))

    @inlineCallbacks
    def test_decompose_raises_when_not_404_error(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        mock_redfish_request = self.patch(driver, 'redfish_request')
        error = PartialDownloadError(
            response=json.dumps(SAMPLE_JSON_SYSTEMS).encode('utf-8'),
            code=HTTPStatus.BAD_REQUEST)
        mock_redfish_request.side_effect = error

        with ExpectedException(PartialDownloadError):
            yield driver.decompose(
                factory.make_name('system_id'), context)
            self.assertThat(mock_redfish_request, MockCalledOnceWith(
                b"DELETE", join(url, endpoint), headers))

    @inlineCallbacks
    def test__set_pxe_boot(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_file_body_producer = self.patch(
            rsd_module, 'FileBodyProducer')
        payload = FileBodyProducer(
            BytesIO(
                json.dumps(
                    {
                        'Boot': {
                            'BootSourceOverrideEnabled': "Once",
                            'BootSourceOverrideTarget': "Pxe"
                        }
                    }).encode('utf-8')))
        mock_file_body_producer.return_value = payload
        mock_redfish_request = self.patch(driver, 'redfish_request')

        yield driver.set_pxe_boot(url, node_id, headers)
        self.assertThat(mock_redfish_request, MockCalledOnceWith(
            b"PATCH", join(url, b"redfish/v1/Nodes/%s" % node_id),
            headers, payload))

    @inlineCallbacks
    def test__get_composed_node_state(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_redfish_request = self.patch(driver, 'redfish_request')
        mock_redfish_request.return_value = SAMPLE_JSON_NODE
        uri = join(url, b"redfish/v1/Nodes/%s" % node_id)

        power_state = yield driver.get_composed_node_state(
            url, node_id, headers)
        self.assertEquals(power_state, "PoweredOff")
        self.assertThat(mock_redfish_request, MockCalledOnceWith(
            b"GET", uri, headers))

    @inlineCallbacks
    def test_assemble_node_does_not_assemble_if_already_assembled(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.return_value = random.choice(
            ["PoweredOn", "PoweredOff"])

        yield driver.assemble_node(url, node_id, headers)
        self.assertThat(mock_get_composed_node_state, MockCalledOnceWith(
            url, node_id, headers))

    @inlineCallbacks
    def test_assemble_node_assembles_if_not_assembled(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.side_effect = [
            "Allocated", "Assembling", "Assembled"]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        endpoint = (
            b"redfish/v1/Nodes/%s/Actions/ComposedNode.Assemble" % node_id)
        uri = join(url, endpoint)

        yield driver.assemble_node(url, node_id, headers)
        self.assertThat(mock_get_composed_node_state, MockCallsMatch(
            call(url, node_id, headers),
            call(url, node_id, headers),
            call(url, node_id, headers)))
        self.assertThat(mock_redfish_request, MockCalledOnceWith(
            b"POST", uri, headers))

    @inlineCallbacks
    def test_assemble_node_raises_error_if_original_power_state_failed(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.return_value = "Failed"
        mock_redfish_request = self.patch(driver, 'redfish_request')

        with ExpectedException(PodFatalError):
            yield driver.assemble_node(url, node_id, headers)
            self.assertThat(mock_get_composed_node_state, MockCalledOnceWith(
                url, node_id, headers))
            self.assertThat(mock_redfish_request, MockNotCalled())

    @inlineCallbacks
    def test_assemble_node_raises_error_if_assembling_fails(self):
        driver = RSDPodDriver()
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.side_effect = [
            "Allocated", "Assembling", "Failed"]
        mock_redfish_request = self.patch(driver, 'redfish_request')
        endpoint = (
            b"redfish/v1/Nodes/%s/Actions/ComposedNode.Assemble" % node_id)
        uri = join(url, endpoint)

        with ExpectedException(PodFatalError):
            yield driver.assemble_node(url, node_id, headers)
            self.assertThat(mock_get_composed_node_state, MockCallsMatch(
                call(url, node_id, headers),
                call(url, node_id, headers),
                call(url, node_id, headers)))
            self.assertThat(mock_redfish_request, MockCalledOnceWith(
                b"POST", uri, headers))

    @inlineCallbacks
    def test_power_issues_power_reset(self):
        driver = RSDPodDriver()
        context = make_context()
        power_change = factory.make_name('power_change')
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_file_body_producer = self.patch(
            rsd_module, 'FileBodyProducer')
        payload = FileBodyProducer(
            BytesIO(
                json.dumps(
                    {
                        'ResetType': "%s" % power_change
                    }).encode('utf-8')))
        mock_file_body_producer.return_value = payload
        mock_redfish_request = self.patch(driver, 'redfish_request')
        expected_uri = join(
            url, b"redfish/v1/Nodes/%s/Actions/ComposedNode.Reset" % node_id)
        yield driver.power(power_change, url, node_id, headers)
        self.assertThat(mock_redfish_request, MockCalledOnceWith(
            b"POST", expected_uri, headers, payload))

    @inlineCallbacks
    def test__power_on(self):
        driver = RSDPodDriver()
        system_id = factory.make_name('system_id')
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_set_pxe_boot = self.patch(driver, 'set_pxe_boot')
        mock_power_query = self.patch(driver, 'power_query')
        mock_power_query.return_value = "on"
        mock_power = self.patch(driver, 'power')

        yield driver.power_on(system_id, context)
        self.assertThat(mock_set_pxe_boot, MockCalledOnceWith(
            url, node_id, headers))
        self.assertThat(mock_power_query, MockCalledOnceWith(
            system_id, context))
        self.assertThat(mock_power, MockCallsMatch(
            call("ForceOff", url, node_id, headers),
            call("On", url, node_id, headers)))

    @inlineCallbacks
    def test__power_off(self):
        driver = RSDPodDriver()
        system_id = factory.make_name('system_id')
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_set_pxe_boot = self.patch(driver, 'set_pxe_boot')
        mock_power = self.patch(driver, 'power')

        yield driver.power_off(system_id, context)
        self.assertThat(mock_set_pxe_boot, MockCalledOnceWith(
            url, node_id, headers))
        self.assertThat(mock_power, MockCalledOnceWith(
            "ForceOff", url, node_id, headers))

    @inlineCallbacks
    def test_power_query_queries_on(self):
        driver = RSDPodDriver()
        power_change = "PoweredOn"
        system_id = factory.make_name('system_id')
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_assemble_node = self.patch(driver, 'assemble_node')
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.return_value = power_change

        power_state = yield driver.power_query(system_id, context)
        self.assertThat(
            mock_assemble_node,
            MockCalledOnceWith(url, node_id, headers))
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers))
        self.assertEquals(power_state, RSD_NODE_POWER_STATE[power_change])

    @inlineCallbacks
    def test_power_query_queries_off(self):
        driver = RSDPodDriver()
        power_change = "PoweredOff"
        system_id = factory.make_name('system_id')
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_assemble_node = self.patch(driver, 'assemble_node')
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.return_value = power_change

        power_state = yield driver.power_query(system_id, context)
        self.assertThat(
            mock_assemble_node,
            MockCalledOnceWith(url, node_id, headers))
        self.assertThat(
            mock_get_composed_node_state,
            MockCalledOnceWith(url, node_id, headers))
        self.assertEquals(power_state, RSD_NODE_POWER_STATE[power_change])

    @inlineCallbacks
    def test_power_query_raises_error_unknown_power_state(self):
        driver = RSDPodDriver()
        system_id = factory.make_name('system_id')
        context = make_context()
        url = driver.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = driver.make_auth_headers(**context)
        mock_assemble_node = self.patch(driver, 'assemble_node')
        mock_get_composed_node_state = self.patch(
            driver, 'get_composed_node_state')
        mock_get_composed_node_state.return_value = "Error"

        with ExpectedException(PodActionError):
            yield driver.power_query(system_id, context)
            self.assertThat(
                mock_assemble_node,
                MockCalledOnceWith(url, node_id, headers))
            self.assertThat(
                mock_get_composed_node_state,
                MockCalledOnceWith(url, node_id, headers))
