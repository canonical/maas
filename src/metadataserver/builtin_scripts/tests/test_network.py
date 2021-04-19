import dataclasses
import json
import random
from typing import List, Optional
from unittest.mock import call

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_TYPE
from maasserver.models.fabric import Fabric
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.subnet import Subnet
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import get_one, reload_object
from metadataserver.builtin_scripts import network as network_module
from metadataserver.builtin_scripts.network import update_node_interfaces
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME
from provisioningserver.utils.network import (
    annotate_with_default_monitored_interfaces,
)

GB = 1000 * 1000 * 1000


@dataclasses.dataclass
class LXDPartition:
    id: str
    read_only: bool = False


@dataclasses.dataclass
class LXDDisk:
    id: str
    size: int = 250 * GB
    partitions: List[LXDPartition] = dataclasses.field(default_factory=list)
    type: str = "sata"
    read_only: bool = False
    removable: bool = False
    rpm: int = 0
    numa_node: int = 0


@dataclasses.dataclass
class LXDVlan:
    lower_device: str
    vid: int


@dataclasses.dataclass
class LXDBridge:
    upper_devices: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class LXDBond:
    lower_devices: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class LXDAddress:

    address: str
    netmask: str
    family: str = "inet"
    scope: str = "global"


@dataclasses.dataclass
class LXDNetwork:
    name: str
    hwaddr: str
    type: str = "broadcast"
    state: str = "up"
    addresses: List[LXDAddress] = dataclasses.field(default_factory=list)
    vlan: Optional[LXDVlan] = None
    bridge: Optional[LXDBridge] = None
    bond: Optional[LXDBond] = None


@dataclasses.dataclass
class LXDNetworkPort:

    id: str
    port: int
    address: str = dataclasses.field(default_factory=factory.make_mac_address)
    protocol: str = "ethernet"
    supported_modes: List[str] = dataclasses.field(
        default_factory=lambda: ["10000baseT/Full"]
    )
    supported_ports: List[str] = dataclasses.field(
        default_factory=lambda: ["fibre"]
    )
    port_type: str = "fibre"
    transceiver_type: str = "internal"
    auto_negotiation: bool = True
    link_detected: bool = True
    link_speed: int = 10000
    link_duplex: str = "full"


@dataclasses.dataclass
class LXDNetworkCard:

    pci_address: str
    vendor: str = "My Corporation"
    vendor_id: str = "1234"
    product: str = "My Gigabit Network Connection"
    product_id: str = "5678"
    firmware_version: str = "1.63, 0x800009fa"
    numa_node: int = 0
    driver: str = "mydriver"
    driver_version: str = "1.2.3"
    ports: List[LXDNetworkPort] = dataclasses.field(default_factory=list)


class FakeCommissioningData:
    """Helper to generate commissioning output programtically.

    Instead of hardcoding the commissioning data, taking care of
    including all the possible keys and values, this class allows you to
    tell which interface you want the machine to have, and you only have
    to specify what's important for the tests. The helper will ensure
    that all the other keys are there with a sane value and in the right
    format.
    """

    def __init__(
        self,
        cores=1,
        memory=2048,
        disks=None,
        api_extensions=None,
        api_version="1.0",
    ):
        self.cores = cores
        self.memory = memory
        if api_extensions is None:
            api_extensions = [
                "resources",
                "resources_v2",
                "api_os",
                "resources_system",
                "resources_usb_pci",
            ]
        self.api_extensions = api_extensions
        self.api_version = api_version
        self.environment = {
            "kernel": "Linux",
            "kernel_architecture": "x86_64",
            "kernel_version": "5.4.0-67-generic",
            "os_name": "ubuntu",
            "os_version": "20.04",
            "server": "maas-machine-resources",
            "server_name": "azuera",
            "server_version": "4.11",
        }
        self.address_annotations = {}
        self._allocated_pci_addresses = []
        self.networks = {}
        self._network_cards = []
        if disks is None:
            disks = [LXDDisk("sda")]
        self._disks = list(disks)
        self.hints = None

    def allocate_pci_address(self):
        prev_address = (
            self._allocated_pci_addresses[-1]
            if self._allocated_pci_addresses
            else "0000:00:00.0"
        )
        bus, device, func = prev_address.split(":")
        next_device = int(device, 16) + 1
        self._allocated_pci_addresses.append(
            f"{bus}:{next_device:0>4x}:{func}"
        )
        return self._allocated_pci_addresses[-1]

    def get_available_vid(self):
        available_vids = set(range(2, 4095))
        used_vids = set(
            [
                network.vlan.vid
                for network in self.networks.values()
                if network.vlan is not None
            ]
        )
        available_vids = list(available_vids.difference(used_vids))
        return random.choice(available_vids)

    def create_physical_network(
        self,
        name=None,
        mac_address=None,
        card=None,
        port=None,
    ):
        if card is None:
            card = LXDNetworkCard(self.allocate_pci_address())
        if name is None:
            name = factory.make_string("eth")
        if mac_address is None:
            mac_address = factory.make_mac_address()
        network = LXDNetwork(name, mac_address)
        self.networks[name] = network
        if port is None:
            port = LXDNetworkPort(name, len(card.ports), address=mac_address)
        card.ports.append(port)
        self._network_cards.append(card)
        return network

    def create_vlan_network(
        self,
        name=None,
        vid=None,
        mac_address=None,
        parent=None,
    ):
        if name is None:
            name = factory.make_string("vlan")
        if parent is None:
            parent = self.create_physical_network()
        if mac_address is None:
            mac_address = factory.make_mac_address()
        if vid is None:
            vid = self.get_available_vid()
        network = LXDNetwork(
            name, mac_address, vlan=LXDVlan(lower_device=parent.name, vid=vid)
        )
        self.networks[name] = network
        return network

    def create_bridge_network(
        self,
        name=None,
        mac_address=None,
        parents=None,
    ):
        if name is None:
            name = factory.make_string("bridge")
        if parents is None:
            parents = [self.create_physical_network()]
        if mac_address is None:
            mac_address = factory.make_mac_address()
        network = LXDNetwork(
            name,
            mac_address,
            bridge=LXDBridge(
                upper_devices=[parent.name for parent in parents]
            ),
        )
        self.networks[name] = network
        return network

    def create_bond_network(
        self,
        name=None,
        mac_address=None,
        parents=None,
    ):
        if name is None:
            name = factory.make_string("bond")
        if parents is None:
            parents = [self.create_physical_network()]
        if mac_address is None:
            mac_address = factory.make_mac_address()
        network = LXDNetwork(
            name,
            mac_address,
            bond=LXDBond(lower_devices=[parent.name for parent in parents]),
        )
        self.networks[name] = network
        return network

    def render(self):
        storage_resources = {
            "disks": [dataclasses.asdict(disk) for disk in self._disks],
            "total": len(self._disks),
        }
        network_resources = {
            "cards": [
                dataclasses.asdict(card) for card in self._network_cards
            ],
            "total": len(self._network_cards),
        }
        networks = dict(
            (name, dataclasses.asdict(network))
            for name, network in self.networks.items()
        )
        data = {
            "api_extensions": self.api_extensions,
            "api_version": self.api_version,
            "environment": self.environment,
            "resources": {
                "cpu": {
                    "architecture": self.environment["kernel_architecture"],
                    "sockets": [
                        {
                            "socket": 0,
                            "cores": [],
                        }
                    ],
                },
                "memory": {
                    "hugepages_total": 0,
                    "hugepages_used": 0,
                    "hugepages_size": 0,
                    "used": int(0.3 * self.memory * 1024 * 1024),
                    "total": int(self.memory * 1024 * 1024),
                },
                "gpu": {"cards": [], "total": 0},
                "network": network_resources,
                "storage": storage_resources,
            },
            "networks": networks,
            "network-extra": {
                "interfaces": self._generate_interfaces(),
                "hints": self.hints,
            },
        }
        for core_index in range(self.cores):
            data["resources"]["cpu"]["sockets"][0]["cores"].append(
                {
                    "core": core_index,
                    "threads": [
                        {
                            "id": core_index,
                            "thread": 0,
                            "online": True,
                            "numa_node": 0,
                        },
                    ],
                    "frequency": 1500,
                }
            )
        return data

    def _generate_interfaces(self):
        # XXX: It would be good if this method could basically call
        # get_all_interfaces_definition(), passing in information it
        # needs. But considering the goal is to minimize information and
        # instead make use of the LXD data directly, it's probably worth
        # holding off until there's less information to render.
        interfaces = {}
        for name, network in self.networks.items():
            interface = {
                "mac_address": self._get_network_port_mac(
                    name, network.hwaddr
                ),
                "links": [],
                "enabled": network.state == "up",
                "source": "machine-resources",
            }
            if network.vlan is not None:
                interface.update(
                    {
                        "type": "vlan",
                        "parents": [network.vlan.lower_device],
                        "vid": network.vlan.vid,
                    }
                )
            elif network.bridge is not None:
                interface.update(
                    {
                        "type": "bridge",
                        "parents": list(network.bridge.upper_devices),
                    }
                )
            elif network.bond is not None:
                interface.update(
                    {
                        "type": "bond",
                        "parents": list(network.bond.lower_devices),
                    }
                )
            else:
                interface.update({"type": "physical", "parents": []})
            for address in network.addresses:
                link = {
                    "address": f"{address.address}/{address.netmask}",
                    "mode": "static",
                }
                address_annotation = self.address_annotations.get(
                    address.address, {}
                )
                link.update(address_annotation)
                interface["links"].append(link)
            interfaces[name] = interface
        annotate_with_default_monitored_interfaces(interfaces)
        return interfaces

    def _get_network_port_mac(self, port_name, default):
        for card in self._network_cards:
            for port in card.ports:
                if port.id == port_name:
                    return port.address

        return default


class UpdateInterfacesMixin:
    def create_empty_controller(self, **kwargs):
        node_type = random.choice(
            [
                NODE_TYPE.REGION_CONTROLLER,
                NODE_TYPE.RACK_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            ]
        )
        return factory.make_Node(node_type=node_type, **kwargs).as_self()

    def update_interfaces(
        self,
        controller,
        data,
        passes=None,
    ):
        data = data.render()
        # update_node_interfaces() is idempotent, so it doesn't matter
        # if it's called once or twice.
        if passes is None:
            passes = random.randint(1, 2)
        for _ in range(passes):
            update_node_interfaces(controller, data)
        return passes


class TestUpdateInterfaces(MAASServerTestCase, UpdateInterfacesMixin):
    def test_all_new_physical_interfaces_no_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.state = "up"
        eth1 = data.create_physical_network(
            "eth1",
            mac_address="22:22:22:22:22:22",
        )
        eth1.state = "down"

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(name="eth0", node=controller)
        self.assertEqual("11:11:11:11:11:11", eth0.mac_address)
        self.assertTrue(eth0.enabled)
        self.assertEqual(
            Fabric.objects.get_default_fabric().get_default_vlan(), eth0.vlan
        )
        self.assertEqual([], list(eth0.parents.all()))
        eth1 = PhysicalInterface.objects.get(name="eth1", node=controller)
        self.assertEqual("22:22:22:22:22:22", eth1.mac_address)
        self.assertFalse(eth1.enabled)
        self.assertIsNone(eth1.vlan)
        self.assertEqual([], list(eth1.parents.all()))

    def test_vlans_with_alternate_naming_conventions(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        data.create_vlan_network("vlan0100", parent=eth0_network)
        data.create_vlan_network("vlan101", parent=eth0_network)
        data.create_vlan_network("eth0.0102", parent=eth0_network)

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(name="eth0", node=controller)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertTrue(eth0.enabled)
        self.assertEqual([], list(eth0.parents.all()))
        vlan0100 = Interface.objects.get(name="vlan0100", node=controller)
        self.assertEqual(INTERFACE_TYPE.VLAN, vlan0100.type)
        # XXX: For some reason MAAS forces VLAN interfaces to have the
        # same MAC as the parent. But in reality, VLAN interfaces may
        # have different MAC addresses.
        self.assertEqual(eth0_network.hwaddr, vlan0100.mac_address)
        self.assertTrue(vlan0100.enabled)
        self.assertEqual([eth0], list(vlan0100.parents.all()))
        vlan101 = Interface.objects.get(name="vlan101", node=controller)
        self.assertEqual(INTERFACE_TYPE.VLAN, vlan101.type)
        # XXX: For some reason MAAS forces VLAN interfaces to have the
        # same MAC as the parent. But in reality, VLAN interfaces may
        # have different MAC addresses.
        self.assertEqual(eth0_network.hwaddr, vlan101.mac_address)
        self.assertTrue(vlan101.enabled)
        self.assertEqual([eth0], list(vlan101.parents.all()))
        eth0_0102 = Interface.objects.get(name="eth0.0102", node=controller)
        self.assertEqual(INTERFACE_TYPE.VLAN, eth0_0102.type)
        # XXX: For some reason MAAS forces VLAN interfaces to have the
        # same MAC as the parent. But in reality, VLAN interfaces may
        # have different MAC addresses.
        self.assertEqual(eth0_network.hwaddr, eth0_0102.mac_address)
        self.assertTrue(eth0_0102.enabled)
        self.assertEqual([eth0], list(eth0_0102.parents.all()))

    def test_sets_discovery_parameters(self):
        controller = self.create_empty_controller()
        eth0_mac = factory.make_mac_address()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=eth0_mac
        )
        data.create_vlan_network(
            "eth0.100", vid=100, parent=eth0_network, mac_address=eth0_mac
        )
        eth1_network = data.create_physical_network("eth1")
        eth1_network.state = "down"

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertTrue(eth0.neighbour_discovery_state)
        self.assertTrue(eth0.mdns_discovery_state)
        eth0_vlan = Interface.objects.get(name="eth0.100", node=controller)
        self.assertFalse(eth0_vlan.neighbour_discovery_state)
        self.assertTrue(eth0_vlan.mdns_discovery_state)
        eth1 = Interface.objects.get(name="eth1", node=controller)
        self.assertFalse(eth1.neighbour_discovery_state)
        self.assertTrue(eth1.mdns_discovery_state)

    def test_clears_discovery_parameters(self):
        controller = self.create_empty_controller()
        eth0_mac = factory.make_mac_address()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=eth0_mac
        )
        vlan_network = data.create_vlan_network(
            "eth0.100", vid=100, parent=eth0_network, mac_address=eth0_mac
        )
        self.update_interfaces(controller, data)

        # Disable the interfaces so that we can make sure neighbour discovery
        # is properly disabled on update.
        eth0_network.state = "down"
        vlan_network.state = "down"

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertFalse(eth0.neighbour_discovery_state)
        self.assertTrue(eth0.mdns_discovery_state)
        eth0_vlan = Interface.objects.get(name="eth0.100", node=controller)
        self.assertFalse(eth0_vlan.neighbour_discovery_state)
        self.assertTrue(eth0_vlan.mdns_discovery_state)

    def test_new_physical_with_new_subnet_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        gateway_ip = factory.pick_ip_in_network(network, but_not=[ip])
        data = FakeCommissioningData()
        eth0 = data.create_physical_network(
            "eth0",
            mac_address="11:11:11:11:11:11",
        )
        eth0.addresses = [LXDAddress(str(ip), network.prefixlen)]
        data.address_annotations[str(ip)] = {"gateway": str(gateway_ip)}
        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual("11:11:11:11:11:11", eth0.mac_address)
        self.assertEqual(default_vlan, eth0.vlan)
        self.assertTrue(eth0.enabled)
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertEqual(str(network.cidr), subnet.name)
        self.assertEqual(default_vlan, subnet.vlan)
        self.assertEqual(gateway_ip, subnet.gateway_ip)
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_new_physical_with_dhcp_link(self):
        controller = self.create_empty_controller()
        network = factory.make_ip4_or_6_network()
        ip = factory.pick_ip_in_network(network)
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress(str(ip), network.prefixlen)]
        data.address_annotations[str(ip)] = {"mode": "dhcp"}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(default_vlan, eth0.vlan)
        dhcp_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
        )
        self.assertEqual([None], [address.ip for address in dhcp_addresses])
        subnet = Subnet.objects.get(cidr=str(network.cidr))
        self.assertEqual(str(network.cidr), subnet.name)
        self.assertEqual(default_vlan, subnet.vlan)
        discovered_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        )
        self.assertEqual(
            [(ip, subnet)],
            [(address.ip, address.subnet) for address in discovered_addresses],
        )

    def test_new_physical_with_multiple_dhcp_link(self):
        controller = self.create_empty_controller()
        network1 = factory.make_ip4_or_6_network()
        ip1 = str(factory.pick_ip_in_network(network1))
        network2 = factory.make_ip4_or_6_network()
        ip2 = str(factory.pick_ip_in_network(network2))
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [
            LXDAddress(ip1, network1.prefixlen),
            LXDAddress(ip2, network2.prefixlen),
        ]
        data.address_annotations[ip1] = {"mode": "dhcp"}
        data.address_annotations[ip2] = {"mode": "dhcp"}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        default_vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(default_vlan, eth0.vlan)
        dhcp_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
        )
        self.assertEqual(
            [None, None], [address.ip for address in dhcp_addresses]
        )
        discovered_addresses = list(
            eth0.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        )
        self.assertEqual(
            sorted([ip1, ip2]),
            sorted([address.ip for address in discovered_addresses]),
        )

    def test_new_physical_with_resource_info(self):
        controller = self.create_empty_controller(with_empty_script_sets=True)
        data = FakeCommissioningData()
        card = LXDNetworkCard(
            data.allocate_pci_address(),
            vendor=factory.make_name("vendor"),
            product=factory.make_name("product"),
            firmware_version=factory.make_name("firmware_version"),
        )
        data.create_physical_network("eth0", card=card)

        self.update_interfaces(controller, data)
        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertEqual(card.vendor, eth0.vendor)
        self.assertEqual(card.product, eth0.product)
        self.assertEqual(card.firmware_version, eth0.firmware_version)

    def test_new_physical_with_existing_subnet_link_with_gateway(self):
        controller = self.create_empty_controller()
        subnet = factory.make_Subnet()
        network = subnet.get_ipnetwork()
        gateway_ip = factory.pick_ip_in_network(network)
        subnet.gateway_ip = gateway_ip
        subnet.save()
        ip = str(factory.pick_ip_in_network(network, but_not=[gateway_ip]))
        diff_gateway_ip = str(
            factory.pick_ip_in_network(network, but_not=[gateway_ip, ip])
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress(ip, network.prefixlen)]
        data.address_annotations[ip] = {"gateway": diff_gateway_ip}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(subnet.vlan, eth0.vlan)

        # Check that the gateway IP didn't change.
        self.assertEqual(gateway_ip, subnet.gateway_ip)
        [eth0_address] = list(eth0.ip_addresses.all())
        self.assertEqual(ip, eth0_address.ip)
        self.assertEqual(IPADDRESS_TYPE.STICKY, eth0_address.alloc_type)
        self.assertEqual(subnet, eth0_address.subnet)

    def test_new_physical_with_existing_subnet_link_without_gateway(self):
        controller = self.create_empty_controller()
        subnet = factory.make_Subnet()
        subnet.gateway_ip = None
        subnet.save()
        network = subnet.get_ipnetwork()
        gateway_ip = str(factory.pick_ip_in_network(network))
        ip = str(factory.pick_ip_in_network(network, but_not=[gateway_ip]))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress(ip, network.prefixlen)]
        data.address_annotations[ip] = {"gateway": gateway_ip}

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(subnet.vlan, eth0.vlan)

        subnet = reload_object(subnet)
        # Check that the gateway IP did get set.
        self.assertEqual(gateway_ip, subnet.gateway_ip)

        [eth0_address] = list(eth0.ip_addresses.all())
        self.assertEqual(ip, eth0_address.ip)
        self.assertEqual(IPADDRESS_TYPE.STICKY, eth0_address.alloc_type)
        self.assertEqual(subnet, eth0_address.subnet)

    def test_new_physical_with_multiple_subnets(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet1 = factory.make_Subnet(vlan=vlan)
        ip1 = str(factory.pick_ip_in_Subnet(subnet1))
        subnet2 = factory.make_Subnet(vlan=vlan)
        ip2 = str(factory.pick_ip_in_Subnet(subnet2))
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [
            LXDAddress(ip1, subnet1.get_ipnetwork().prefixlen),
            LXDAddress(ip2, subnet2.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        eth0 = Interface.objects.get(name="eth0", node=controller)
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        eth0_addresses = list(eth0.ip_addresses.order_by("id"))
        self.assertEqual(
            [
                (IPADDRESS_TYPE.STICKY, ip1, subnet1),
                (IPADDRESS_TYPE.STICKY, ip2, subnet2),
            ],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_existing_physical_with_existing_static_link(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.interface_set.all()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        eth0_addresses = list(interface.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_existing_physical_with_existing_auto_link(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.interface_set.all()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(interface.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

    def test_existing_physical_removes_old_links(self):
        controller = self.create_empty_controller()
        vlan = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        extra_ips = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                subnet=subnet,
                interface=interface,
            )
            for _ in range(3)
        ]
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        [eth0] = controller.interface_set.all()
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(interface.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        for extra_ip in extra_ips:
            self.assertIsNone(reload_object(extra_ip))

    def test_existing_physical_with_links_new_vlan_no_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        vid_on_fabric = random.randint(1, 4094)

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]
        data.create_vlan_network(
            f"eth0.{vid_on_fabric}", parent=eth0_network, vid=vid_on_fabric
        )

        self.update_interfaces(controller, data)

        self.assertEqual(2, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=created_vlan
        )
        self.assertEqual(f"eth0.{vid_on_fabric}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)
        self.assertTrue(created_vlan, vlan_interface.vlan)

    def test_existing_physical_with_links_new_vlan_new_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        vid_on_fabric = random.randint(1, 4094)
        vlan_ipnetwork = factory.make_ip4_or_6_network()
        vlan_ip = factory.pick_ip_in_network(vlan_ipnetwork)

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]
        vlan_network = data.create_vlan_network(
            f"eth0.{vid_on_fabric}", parent=eth0_network, vid=vid_on_fabric
        )
        vlan_network.addresses = [
            LXDAddress(vlan_ip, vlan_ipnetwork.prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(2, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=created_vlan
        )
        self.assertEqual(f"eth0.{vid_on_fabric}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)
        self.assertTrue(created_vlan, vlan_interface.vlan)

        vlan_subnet = Subnet.objects.get(cidr=str(vlan_ipnetwork.cidr))
        self.assertEqual(created_vlan, vlan_subnet.vlan)
        self.assertEqual(str(vlan_ipnetwork.cidr), vlan_subnet.name)

        vlan_addresses = list(vlan_interface.ip_addresses.all())
        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, vlan_ip, vlan_subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in vlan_addresses
            ],
        )

    def test_existing_physical_with_links_new_vlan_other_subnet_vid(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        vid_on_fabric = random.randint(1, 4094)
        other_subnet = factory.make_Subnet()
        vlan_ip = factory.pick_ip_in_Subnet(other_subnet)

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        eth0_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]
        vlan_network = data.create_vlan_network(
            f"eth0.{vid_on_fabric}", parent=eth0_network, vid=vid_on_fabric
        )
        vlan_network.addresses = [
            LXDAddress(vlan_ip, other_subnet.get_ipnetwork().prefixlen),
        ]

        maaslog = self.patch(network_module, "maaslog")
        passes = self.update_interfaces(controller, data)

        self.assertEqual(2, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)
        eth0_addresses = list(eth0.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in eth0_addresses
            ],
        )

        self.assertFalse(
            VLAN.objects.filter(fabric=fabric, vid=vid_on_fabric).exists()
        )
        other_vlan = other_subnet.vlan
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=other_vlan
        )
        self.assertEqual(f"eth0.{vid_on_fabric}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)
        self.assertEqual(vlan_interface.ip_addresses.count(), 1)
        self.assertEqual(
            maaslog.method_calls,
            [
                call.error(
                    f"Interface 'eth0' on controller '{controller.hostname}' "
                    f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                ),
                call.error(
                    f"VLAN interface '{vlan_interface.name}' reports VLAN {vid_on_fabric} "
                    f"but links are on VLAN {other_vlan.vid}"
                ),
            ]
            * passes,
        )

    def test_existing_physical_with_no_links_new_vlan_no_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        vid_on_fabric = random.randint(1, 4094)
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            f"eth0.{vid_on_fabric}", vid=vid_on_fabric, parent=eth0_network
        )
        self.update_interfaces(controller, data)
        self.assertEqual(2, controller.interface_set.count())
        [physical] = controller.interface_set.filter(
            type=INTERFACE_TYPE.PHYSICAL
        )
        self.assertEqual("eth0", physical.name)
        self.assertEqual(eth0_network.hwaddr, physical.mac_address)
        self.assertEqual(vlan, physical.vlan)
        self.assertTrue(physical.enabled)

        created_vlan = VLAN.objects.get(fabric=fabric, vid=vid_on_fabric)
        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=created_vlan
        )
        [vlan_interface] = controller.interface_set.filter(
            type=INTERFACE_TYPE.VLAN
        )
        self.assertEqual(vlan_network.name, vlan_interface.name)
        self.assertEqual(created_vlan, vlan_interface.vlan)
        self.assertTrue(vlan_interface.enabled)

    def test_existing_physical_with_no_links_new_vlan_with_links(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        other_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=other_fabric)
        subnet = factory.make_Subnet(vlan=new_vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            f"eth0.{new_vlan.vid}", parent=eth0_network, vid=new_vlan.vid
        )
        vlan_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        maaslog = self.patch(network_module, "maaslog")
        passes = self.update_interfaces(controller, data)

        self.assertEqual(2, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(fabric.get_default_vlan(), eth0.vlan)

        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=new_vlan
        )
        self.assertEqual(f"eth0.{new_vlan.vid}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)

        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, ip, subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in vlan_addresses
            ],
        )
        self.assertEqual(
            maaslog.method_calls,
            [
                call.error(
                    f"Interface 'eth0' on controller '{controller.hostname}' "
                    f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                )
            ]
            * passes,
        )

    def test_existing_physical_with_no_links_vlan_with_other_subnet(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, name="eth0", vlan=vlan
        )
        other_vlan = factory.make_VLAN(fabric=fabric)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            name=f"eth0.{other_vlan.vid}",
            vlan=other_vlan,
            parents=[interface],
        )

        new_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=new_fabric)
        new_subnet = factory.make_Subnet(vlan=new_vlan)
        ip = str(factory.pick_ip_in_Subnet(new_subnet))
        links_to_remove = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY, interface=vlan_interface
            )
            for _ in range(3)
        ]

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            f"eth0.{other_vlan.vid}", parent=eth0_network, vid=other_vlan.vid
        )
        vlan_network.addresses = [
            LXDAddress(ip, new_subnet.get_ipnetwork().prefixlen),
        ]

        maaslog = self.patch(network_module, "maaslog")
        passes = self.update_interfaces(controller, data)

        self.assertEqual(2, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=new_vlan
        )
        self.assertEqual(f"eth0.{other_vlan.vid}", vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)

        self.assertCountEqual(
            vlan_interface.ip_addresses.values_list("ip", flat=True), [ip]
        )
        self.assertEqual(
            maaslog.method_calls,
            [
                call.error(
                    f"Interface 'eth0' on controller '{controller.hostname}' "
                    f"is not on the same fabric as VLAN interface '{vlan_interface.name}'."
                ),
                call.error(
                    f"VLAN interface '{vlan_interface.name}' reports VLAN {other_vlan.vid} "
                    f"but links are on VLAN {new_vlan.vid}"
                ),
            ]
            * passes,
        )
        for link in links_to_remove:
            self.assertIsNone(reload_object(link))

    def test_existing_vlan_interface_different_fabric_from_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, name="eth0", vlan=vlan
        )
        subnet = factory.make_Subnet(vlan=vlan)
        ip = factory.pick_ip_in_Subnet(subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=ip,
            subnet=subnet,
            interface=interface,
        )
        new_fabric = factory.make_Fabric()
        new_vlan = factory.make_VLAN(fabric=new_fabric)
        vlan_subnet = factory.make_Subnet(vlan=new_vlan)
        vlan_ip = str(factory.pick_ip_in_Subnet(vlan_subnet))
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=new_vlan,
            parents=[interface],
        )
        vlan_name = vlan_interface.name

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(interface.mac_address)
        )
        vlan_network = data.create_vlan_network(
            vlan_name, parent=eth0_network, vid=new_vlan.vid
        )
        vlan_network.addresses = [
            LXDAddress(vlan_ip, vlan_subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(2, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(interface.mac_address, eth0.mac_address)
        self.assertEqual(vlan, eth0.vlan)

        vlan_interface = VLANInterface.objects.get(
            node=controller, vlan=new_vlan
        )
        self.assertEqual(vlan_name, vlan_interface.name)
        self.assertTrue(vlan_interface.enabled)

        vlan_addresses = list(vlan_interface.ip_addresses.all())
        self.assertEqual(
            [(IPADDRESS_TYPE.STICKY, vlan_ip, vlan_subnet)],
            [
                (address.alloc_type, address.ip, address.subnet)
                for address in vlan_addresses
            ],
        )

    def test_bond_with_existing_parents(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network, eth1_network]
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.interface_set.count())
        bond_interface = BondInterface.objects.get(
            node=controller,
            mac_address=bond_network.hwaddr,
        )
        self.assertEqual("bond0", bond_interface.name)
        self.assertTrue(bond_interface.enabled)
        self.assertEqual(vlan, bond_interface.vlan)
        self.assertEqual(
            sorted(parent.name for parent in bond_interface.parents.all()),
            ["eth0", "eth1"],
        )

    def test_bridge_with_existing_parents(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bridge_network = data.create_bridge_network(
            "br0",
            mac_address=str(eth1.mac_address),
            parents=[eth0_network, eth1_network],
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.interface_set.count())
        bridge_interface = BridgeInterface.objects.get(
            node=controller, mac_address=bridge_network.hwaddr
        )
        self.assertEqual("br0", bridge_interface.name)
        self.assertEqual(vlan, bridge_interface.vlan)
        self.assertEqual(
            sorted(parent.name for parent in bridge_interface.parents.all()),
            ["eth0", "eth1"],
        )

    def test_bond_updates_existing_bond(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_Interface(
            INTERFACE_TYPE.BOND,
            vlan=vlan,
            parents=[eth0, eth1],
            node=controller,
            name="bond0",
            mac_address=factory.make_mac_address(),
        )
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        data.create_physical_network("eth1", mac_address=str(eth1.mac_address))
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network]
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.interface_set.count())
        bond_interface = BondInterface.objects.get(
            node=controller, mac_address=bond_network.hwaddr
        )
        self.assertEqual("bond0", bond_interface.name)
        self.assertEqual(vlan, bond_interface.vlan)
        self.assertEqual(
            sorted(parent.name for parent in bond_interface.parents.all()),
            ["eth0"],
        )

    def test_bridge_updates_existing_bridge(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            vlan=vlan,
            parents=[eth0, eth1],
            node=controller,
            name="br0",
            mac_address=factory.make_mac_address(),
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        data.create_physical_network("eth1", mac_address=str(eth1.mac_address))
        bridge_network = data.create_bridge_network(
            "br0", parents=[eth0_network]
        )

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.interface_set.count())
        bridge_interface = BridgeInterface.objects.get(
            node=controller, mac_address=bridge_network.hwaddr
        )
        self.assertEqual("br0", bridge_interface.name)
        self.assertEqual(vlan, bridge_interface.vlan)
        self.assertEqual(
            sorted(parent.name for parent in bridge_interface.parents.all()),
            ["eth0"],
        )

    def test_bond_creates_link_updates_parent_vlan(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan
        )
        other_fabric = factory.make_Fabric()
        bond0_vlan = other_fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=bond0_vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network, eth1_network]
        )
        bond_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, str(eth0.mac_address))
        self.assertEqual(bond0_vlan, eth0.vlan)

        eth1 = Interface.objects.get(node=controller, name="eth1")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth1.type)
        self.assertEqual(eth1_network.hwaddr, str(eth1.mac_address))
        self.assertEqual(bond0_vlan, eth1.vlan)
        bond0 = get_one(Interface.objects.filter_by_ip(ip))
        self.assertEqual(INTERFACE_TYPE.BOND, bond0.type)
        self.assertEqual(bond_network.hwaddr, str(bond0.mac_address))
        self.assertEqual(bond0_vlan, bond0.vlan)
        self.assertEqual(
            sorted(parent.name for parent in bond0.parents.all()),
            ["eth0", "eth1"],
        )

    def test_bridge_creates_link_updates_parent_vlan(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[eth0, eth1], vlan=vlan
        )
        other_fabric = factory.make_Fabric()
        br0_vlan = other_fabric.get_default_vlan()
        subnet = factory.make_Subnet(vlan=br0_vlan)
        ip = str(factory.pick_ip_in_Subnet(subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=str(eth0.mac_address)
        )
        eth1_network = data.create_physical_network(
            "eth1", mac_address=str(eth1.mac_address)
        )
        bridge_network = data.create_bridge_network(
            "br0",
            parents=[eth0_network, eth1_network],
            mac_address=str(br0.mac_address),
        )
        bridge_network.addresses = [
            LXDAddress(ip, subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        self.assertEqual(3, controller.interface_set.count())
        eth0 = Interface.objects.get(node=controller, name="eth0")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth0.type)
        self.assertEqual(eth0_network.hwaddr, str(eth0.mac_address))
        self.assertEqual(br0_vlan, eth0.vlan)

        eth1 = Interface.objects.get(node=controller, name="eth1")
        self.assertEqual(INTERFACE_TYPE.PHYSICAL, eth1.type)
        self.assertEqual(eth1_network.hwaddr, str(eth1.mac_address))
        self.assertEqual(br0_vlan, eth1.vlan)
        br0 = get_one(Interface.objects.filter_by_ip(ip))
        self.assertEqual(INTERFACE_TYPE.BRIDGE, br0.type)
        self.assertEqual(bridge_network.hwaddr, str(br0.mac_address))
        self.assertEqual(br0_vlan, br0.vlan)
        self.assertEqual(
            sorted(parent.name for parent in br0.parents.all()),
            ["eth0", "eth1"],
        )

    def test_bridge_with_mac_as_phyisical_not_updated(self):
        controller = self.create_empty_controller(with_empty_script_sets=True)
        mac_address = factory.make_mac_address()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, mac_address=mac_address
        )
        factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[eth0], mac_address=mac_address
        )

        data = FakeCommissioningData()
        card = LXDNetworkCard(
            data.allocate_pci_address(),
            vendor=factory.make_name("vendor"),
            product=factory.make_name("product"),
            firmware_version=factory.make_name("firmware_version"),
        )
        eth0_network = data.create_physical_network(
            "eth0",
            mac_address=mac_address,
            card=card,
        )
        data.create_bridge_network(
            "br0",
            parents=[eth0_network],
            mac_address=mac_address,
        )

        lxd_script = (
            controller.current_commissioning_script_set.find_script_result(
                script_name=LXD_OUTPUT_NAME
            )
        )
        lxd_script_output = data.render()
        lxd_script.store_result(
            0, stdout=json.dumps(lxd_script_output).encode("utf-8")
        )

        self.update_interfaces(controller, data)

        br0 = Interface.objects.get(name="br0", node=controller)
        self.assertNotEqual(card.vendor, br0.vendor)
        self.assertNotEqual(card.product, br0.product)
        self.assertNotEqual(card.firmware_version, br0.firmware_version)

    def test_removes_missing_interfaces(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan
        )
        data = FakeCommissioningData()

        self.update_interfaces(controller, data)

        self.assertIsNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNone(reload_object(bond0))

    def test_removes_one_bond_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, name="bond0", parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )
        data.create_bond_network(
            "bond0",
            parents=[eth0_network],
            mac_address=str(bond0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(bond0))

    def test_removes_one_bridge_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, name="br0", parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )
        data.create_bridge_network(
            "br0",
            parents=[eth0_network],
            mac_address=str(br0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNotNone(reload_object(br0))

    def test_removes_one_bond_and_one_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNone(reload_object(bond0))

    def test_removes_one_bridge_and_one_parent(self):
        controller = self.create_empty_controller()
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=controller, vlan=vlan
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[eth0, eth1], vlan=vlan
        )

        data = FakeCommissioningData()
        data.create_physical_network(
            "eth0",
            mac_address=str(eth0.mac_address),
        )

        self.update_interfaces(controller, data)

        self.assertIsNotNone(reload_object(eth0))
        self.assertIsNone(reload_object(eth1))
        self.assertIsNone(reload_object(br0))

    def test_all_new_bond_with_vlan(self):
        controller = self.create_empty_controller()
        bond0_fabric = factory.make_Fabric()
        bond0_untagged = bond0_fabric.get_default_vlan()
        bond0_subnet = factory.make_Subnet(vlan=bond0_untagged)
        bond0_ip = str(factory.pick_ip_in_Subnet(bond0_subnet))
        bond0_vlan = factory.make_VLAN(fabric=bond0_fabric)
        bond0_vlan_subnet = factory.make_Subnet(vlan=bond0_vlan)
        bond0_vlan_ip = str(factory.pick_ip_in_Subnet(bond0_vlan_subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth1_network = data.create_physical_network("eth1")
        bond_network = data.create_bond_network(
            "bond0", parents=[eth0_network, eth1_network]
        )
        bond_network.addresses = [
            LXDAddress(bond0_ip, bond0_subnet.get_ipnetwork().prefixlen),
        ]
        bond_vlan_network = data.create_vlan_network(
            f"bond0.{bond0_vlan.vid}", parent=bond_network, vid=bond0_vlan.vid
        )
        bond_vlan_network.addresses = [
            LXDAddress(
                bond0_vlan_ip, bond0_vlan_subnet.get_ipnetwork().prefixlen
            ),
        ]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node=controller,
            mac_address=eth0_network.hwaddr,
        )
        self.assertEqual("eth0", eth0.name)
        self.assertTrue(eth0.enabled)
        self.assertEqual(bond0_untagged, eth0.vlan)
        eth1 = PhysicalInterface.objects.get(
            node=controller,
            mac_address=eth1_network.hwaddr,
        )
        self.assertEqual("eth1", eth1.name)
        self.assertTrue(eth1.enabled)
        self.assertEqual(bond0_untagged, eth1.vlan)
        bond0 = BondInterface.objects.get(
            node=controller,
            mac_address=bond_network.hwaddr,
        )
        self.assertEqual("bond0", bond0.name)
        self.assertTrue(bond0.enabled)
        self.assertEqual(bond0_untagged, bond0.vlan)
        self.assertItemsEqual(
            [parent.name for parent in bond0.parents.all()],
            ["eth0", "eth1"],
        )
        bond0_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in bond0.ip_addresses.all()
        ]
        self.assertItemsEqual(
            [(IPADDRESS_TYPE.STICKY, bond0_ip, bond0_subnet)], bond0_addresses
        )
        bond0_vlan_nic = VLANInterface.objects.get(
            node=controller, vlan=bond0_vlan
        )
        self.assertEqual(f"bond0.{bond0_vlan.vid}", bond0_vlan_nic.name)
        self.assertTrue(bond0_vlan_nic.enabled)
        self.assertEqual(bond0_vlan, bond0_vlan_nic.vlan)
        self.assertEqual(
            [parent.name for parent in bond0_vlan_nic.parents.all()],
            ["bond0"],
        )
        bond0_vlan_nic_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in bond0_vlan_nic.ip_addresses.all()
        ]
        self.assertItemsEqual(
            [(IPADDRESS_TYPE.STICKY, bond0_vlan_ip, bond0_vlan_subnet)],
            bond0_vlan_nic_addresses,
        )

    def test_all_new_bridge_with_vlan(self):
        controller = self.create_empty_controller()
        br0_fabric = factory.make_Fabric()
        br0_untagged = br0_fabric.get_default_vlan()
        br0_subnet = factory.make_Subnet(vlan=br0_untagged)
        br0_ip = str(factory.pick_ip_in_Subnet(br0_subnet))
        br0_vlan = factory.make_VLAN(fabric=br0_fabric)
        br0_vlan_subnet = factory.make_Subnet(vlan=br0_vlan)
        br0_vlan_ip = str(factory.pick_ip_in_Subnet(br0_vlan_subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth1_network = data.create_physical_network("eth1")
        bridge_network = data.create_bridge_network(
            "br0", parents=[eth0_network, eth1_network]
        )
        bridge_network.addresses = [
            LXDAddress(br0_ip, br0_subnet.get_ipnetwork().prefixlen),
        ]
        bond_vlan_network = data.create_vlan_network(
            f"br0.{br0_vlan.vid}", parent=bridge_network, vid=br0_vlan.vid
        )
        bond_vlan_network.addresses = [
            LXDAddress(br0_vlan_ip, br0_vlan_subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node=controller,
            mac_address=eth0_network.hwaddr,
        )
        self.assertEqual("eth0", eth0.name)
        self.assertTrue(eth0.enabled)
        self.assertEqual(br0_untagged, eth0.vlan)
        eth1 = PhysicalInterface.objects.get(
            node=controller,
            mac_address=eth1_network.hwaddr,
        )
        self.assertEqual("eth1", eth1.name)
        self.assertTrue(eth1.enabled)
        self.assertEqual(br0_untagged, eth1.vlan)

        br0 = BridgeInterface.objects.get(
            node=controller,
            mac_address=bridge_network.hwaddr,
        )
        self.assertEqual("br0", br0.name)
        self.assertTrue(br0.enabled)
        self.assertEqual(br0_untagged, br0.vlan)
        self.assertItemsEqual(
            [parent.name for parent in br0.parents.all()],
            ["eth0", "eth1"],
        )
        br0_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in br0.ip_addresses.all()
        ]
        self.assertItemsEqual(
            [(IPADDRESS_TYPE.STICKY, br0_ip, br0_subnet)], br0_addresses
        )
        br0_vlan_nic = VLANInterface.objects.get(
            node=controller, vlan=br0_vlan
        )
        self.assertEqual(f"br0.{br0_vlan.vid}", br0_vlan_nic.name)
        self.assertTrue(br0_vlan_nic.enabled)
        self.assertEqual(br0_vlan, br0_vlan_nic.vlan)
        self.assertEqual(
            [parent.name for parent in br0_vlan_nic.parents.all()],
            ["br0"],
        )
        br0_vlan_nic_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in br0_vlan_nic.ip_addresses.all()
        ]
        self.assertItemsEqual(
            [(IPADDRESS_TYPE.STICKY, br0_vlan_ip, br0_vlan_subnet)],
            br0_vlan_nic_addresses,
        )

    def test_two_controllers_with_similar_configurations_bug_1563701(self):
        data1 = FakeCommissioningData()
        ens3_network = data1.create_physical_network(
            "ens3", mac_address="52:54:00:ff:0a:cf"
        )
        ens3_network.addresses = [LXDAddress("10.2.0.2", 20)]
        ens4_network = data1.create_physical_network(
            "ens4", mac_address="52:54:00:ab:da:de"
        )
        ens4_network.addresses = [LXDAddress("192.168.35.43", 22)]
        data1.address_annotations["192.168.35.43"] = {
            "mode": "dhcp",
            "gateway": "192.168.32.2",
        }
        ens5_network = data1.create_physical_network(
            "ens5", mac_address="52:54:00:70:8f:5b"
        )
        for vid in range(10, 17):
            vlan_network = data1.create_vlan_network(
                f"ens5.{vid}", parent=ens5_network
            )
            vlan_network.addresses = [LXDAddress(f"10.{vid}.0.2", "20")]

        data2 = FakeCommissioningData()
        ens3_network = data2.create_physical_network(
            "ens3", mac_address="52:54:00:02:eb:bc"
        )
        ens3_network.addresses = [LXDAddress("10.2.0.3", 20)]
        ens4_network = data2.create_physical_network(
            "ens4", mac_address="52:54:00:bc:b0:85"
        )
        ens4_network.addresses = [LXDAddress("192.168.33.246", 22)]
        data2.address_annotations["192.168.33.246"] = {
            "mode": "dhcp",
            "gateway": "192.168.32.2",
        }
        ens5_network = data2.create_physical_network(
            "ens5", mac_address="52:54:00:cf:f3:7f"
        )
        for vid in range(10, 17):
            vlan_network = data2.create_vlan_network(
                f"ens5.{vid}", parent=ens5_network
            )
            vlan_network.addresses = [LXDAddress(f"10.{vid}.0.3", "20")]

        controller1 = self.create_empty_controller()
        controller2 = self.create_empty_controller()
        self.update_interfaces(controller1, data1)
        self.update_interfaces(controller2, data2)
        r1_ens5_16 = get_one(Interface.objects.filter_by_ip("10.16.0.2"))
        self.assertIsNotNone(r1_ens5_16)
        r2_ens5_16 = get_one(Interface.objects.filter_by_ip("10.16.0.3"))
        self.assertIsNotNone(r2_ens5_16)

    def test_all_new_bridge_on_vlan_interface_with_identical_macs(self):
        controller = self.create_empty_controller()
        default_vlan = VLAN.objects.get_default_vlan()
        br0_fabric = factory.make_Fabric()
        eth0_100_vlan = factory.make_VLAN(vid=100, fabric=br0_fabric)
        br0_subnet = factory.make_Subnet(vlan=eth0_100_vlan)
        br0_ip = str(factory.pick_ip_in_Subnet(br0_subnet))
        eth0_mac = factory.make_mac_address()
        br1_fabric = factory.make_Fabric()
        eth1_100_vlan = factory.make_VLAN(vid=100, fabric=br1_fabric)
        br1_subnet = factory.make_Subnet(vlan=eth1_100_vlan)
        br1_ip = str(factory.pick_ip_in_Subnet(br1_subnet))
        eth1_mac = factory.make_mac_address()
        eth0_101_vlan = factory.make_VLAN(vid=101, fabric=br1_fabric)
        br101_subnet = factory.make_Subnet(vlan=eth0_101_vlan)
        br101_ip = str(factory.pick_ip_in_Subnet(br101_subnet))

        data = FakeCommissioningData()
        eth0_network = data.create_physical_network(
            "eth0", mac_address=eth0_mac
        )
        eth0_100_network = data.create_vlan_network(
            "eth0.100", mac_address=eth0_mac, parent=eth0_network, vid=100
        )
        eth0_101_network = data.create_vlan_network(
            "eth0.101", mac_address=eth0_mac, parent=eth0_network, vid=101
        )
        br0_network = data.create_bridge_network(
            "br0", mac_address=eth0_mac, parents=[eth0_100_network]
        )
        br0_network.addresses = [
            LXDAddress(br0_ip, br0_subnet.get_ipnetwork().prefixlen),
        ]
        br101_network = data.create_bridge_network(
            "br101", mac_address=eth0_mac, parents=[eth0_101_network]
        )
        br101_network.addresses = [
            LXDAddress(br101_ip, br101_subnet.get_ipnetwork().prefixlen),
        ]
        data.create_physical_network("eth1", mac_address=eth1_mac)
        eth1_100_network = data.create_vlan_network(
            "eth1.100", mac_address=eth1_mac, parent=eth0_network, vid=100
        )
        br1_network = data.create_bridge_network(
            "br1", mac_address=eth1_mac, parents=[eth1_100_network]
        )
        br1_network.addresses = [
            LXDAddress(br1_ip, br1_subnet.get_ipnetwork().prefixlen),
        ]

        self.update_interfaces(controller, data)

        eth0 = PhysicalInterface.objects.get(
            node=controller, mac_address=eth0_mac
        )
        self.assertEqual("eth0", eth0.name)
        self.assertTrue(eth0.enabled)
        self.assertEqual(default_vlan, eth0.vlan)
        eth0_100 = VLANInterface.objects.get(
            node=controller,
            name="eth0.100",
            mac_address=eth0_mac,
        )
        self.assertTrue(eth0_100.enabled)
        self.assertEqual(eth0_100_vlan, eth0_100.vlan)
        br0 = BridgeInterface.objects.get(
            node=controller,
            name="br0",
            mac_address=eth0_mac,
        )
        self.assertTrue(br0.enabled)
        self.assertEqual(eth0_100_vlan, br0.vlan)
        br0_addresses = [
            (address.alloc_type, address.ip, address.subnet)
            for address in br0.ip_addresses.all()
        ]
        self.assertItemsEqual(
            [(IPADDRESS_TYPE.STICKY, br0_ip, br0_subnet)], br0_addresses
        )
        br0_nic = BridgeInterface.objects.get(
            node=controller, vlan=eth0_100_vlan
        )
        self.assertEqual("br0", br0_nic.name)
        self.assertTrue(br0_nic.enabled)
        self.assertEqual(eth0_100_vlan, br0_nic.vlan)

    def test_registers_bridge_with_disabled_parent(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        eth0_network = data.create_physical_network("eth0")
        eth0_network.addresses = [LXDAddress("10.0.0.2", 24)]
        data.address_annotations["10.0.0.2"] = {"gateway": "10.0.0.1"}
        virbr_nic_network = data.create_physical_network("virbr0-nic")
        virbr_nic_network.state = "down"
        virbr_network = data.create_bridge_network(
            "virbr0",
            mac_address=virbr_nic_network.hwaddr,
            parents=[virbr_nic_network],
        )
        virbr_network.addresses = [LXDAddress("192.168.122.1", 24)]

        self.update_interfaces(controller, data)

        subnet = get_one(Subnet.objects.filter(cidr="10.0.0.0/24"))
        self.assertIsNotNone(subnet)
        subnet = get_one(Subnet.objects.filter(cidr="192.168.122.0/24"))
        self.assertIsNotNone(subnet)

    def test_registers_bridge_with_no_parents_and_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        br0_network = data.create_bridge_network("br0", parents=[])
        br0_network.addresses = [LXDAddress("192.168.0.1", 24)]

        self.update_interfaces(controller, data)

        eth0 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth0")
        )
        br0 = get_one(
            BridgeInterface.objects.filter(node=controller, name="br0")
        )
        self.assertIsNotNone(eth0)
        self.assertIsNotNone(br0)
        subnet = get_one(Subnet.objects.filter(cidr="192.168.0.0/24"))
        self.assertIsNotNone(subnet)
        self.assertEqual(subnet.vlan, br0.vlan)

    def test_registers_bridge_with_no_parents_and_no_links(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_bridge_network("br0", parents=[])
        data.create_physical_network("eth0")

        self.update_interfaces(controller, data)

        eth0 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth0")
        )
        br0 = get_one(
            BridgeInterface.objects.filter(node=controller, name="br0")
        )
        self.assertIsNotNone(eth0)
        self.assertIsNotNone(br0)

    def test_disabled_interfaces_do_not_create_fabrics(self):
        controller = self.create_empty_controller()
        data = FakeCommissioningData()
        data.create_physical_network("eth0")
        eth1_network = data.create_physical_network("eth1")
        eth1_network.state = "down"

        self.update_interfaces(controller, data)

        eth0 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth0")
        )
        eth1 = get_one(
            PhysicalInterface.objects.filter(node=controller, name="eth1")
        )
        self.assertIsNotNone(eth0.vlan)
        self.assertIsNone(eth1.vlan)

    def test_subnet_seen_on_second_controller_does_not_create_fabric(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        alice_data = FakeCommissioningData()
        alice_eth0_network = alice_data.create_physical_network("eth0")
        alice_eth0_network.addresses = [LXDAddress("192.168.0.1", 24)]
        alice_eth1_network = alice_data.create_physical_network("eth1")
        alice_eth1_network.state = "down"

        bob_data = FakeCommissioningData()
        bob_eth0_network = bob_data.create_physical_network("eth0")
        bob_eth0_network.addresses = [LXDAddress("192.168.0.2", 24)]
        bob_eth1_network = bob_data.create_physical_network("eth1")
        bob_eth1_network.state = "down"

        self.update_interfaces(alice, alice_data)

        self.update_interfaces(bob, bob_data)
        alice_eth0 = get_one(
            PhysicalInterface.objects.filter(node=alice, name="eth0")
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth0")
        )
        self.assertEqual(alice_eth0.vlan, bob_eth0.vlan)


class TestUpdateInterfacesWithHints(
    MAASTransactionServerTestCase, UpdateInterfacesMixin
):
    def test_seen_on_second_controller(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        factory.make_Node()
        alice_data = FakeCommissioningData()
        alice_data.create_physical_network("eth0")
        alice_data.networks["eth0"].addresses = [LXDAddress("192.168.0.1", 24)]
        alice_data.address_annotations["192.168.0.1"] = {"mode": "dhcp"}
        alice_data.create_physical_network("eth1")
        alice_data.networks["eth1"].state = "down"

        bob_data = FakeCommissioningData()
        bob_data.create_physical_network("eth0")
        bob_data.create_physical_network("eth1")
        bob_data.hints = [
            {
                "hint": "same_local_fabric_as",
                "ifname": "eth0",
                "related_ifname": "eth1",
            },
            {
                "hint": "on_remote_network",
                "ifname": "eth0",
                "related_ifname": "eth0",
                "related_mac": alice_data.networks["eth0"].hwaddr,
            },
            {
                "hint": "routable_to",
                "ifname": "eth0",
                "related_ifname": "eth0",
                "related_mac": alice_data.networks["eth0"].hwaddr,
            },
            {
                "hint": "rx_own_beacon_on_other_interface",
                "ifname": "eth1",
                "related_ifname": "eth0",
            },
        ]
        self.update_interfaces(alice, alice_data)
        self.update_interfaces(bob, bob_data)
        alice_eth0 = get_one(
            PhysicalInterface.objects.filter(node=alice, name="eth0")
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth0")
        )
        bob_eth1 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth1")
        )
        # Registration with beaconing; we should see all these interfaces
        # appear on the same VLAN.
        self.assertEqual(alice_eth0.vlan, bob_eth0.vlan)
        self.assertEqual(bob_eth1.vlan, bob_eth0.vlan)

    def test_bridge_seen_on_second_controller(self):
        alice = self.create_empty_controller()
        bob = self.create_empty_controller()
        factory.make_Node()
        alice_data = FakeCommissioningData()
        alice_data.create_bridge_network("br0", parents=[])
        alice_data.networks["br0"].addresses = [LXDAddress("192.168.0.1", 24)]
        alice_data.address_annotations["192.168.0.1"] = {"mode": "dhcp"}
        alice_data.create_physical_network("eth1")
        alice_data.networks["eth1"].state = "down"

        bob_data = FakeCommissioningData()
        bob_data.create_physical_network("eth0")
        bob_data.create_physical_network("eth1")
        bob_data.hints = [
            {
                "hint": "same_local_fabric_as",
                "ifname": "eth0",
                "related_ifname": "eth1",
            },
            {
                "hint": "on_remote_network",
                "ifname": "eth0",
                "related_ifname": "br0",
                "related_mac": alice_data.networks["br0"].hwaddr,
            },
            {
                "hint": "routable_to",
                "ifname": "eth0",
                "related_ifname": "br0",
                "related_mac": alice_data.networks["br0"].hwaddr,
            },
            {
                "hint": "rx_own_beacon_on_other_interface",
                "ifname": "eth1",
                "related_ifname": "eth0",
            },
        ]
        self.update_interfaces(alice, alice_data)
        self.update_interfaces(bob, bob_data)
        alice_br0 = get_one(
            BridgeInterface.objects.filter(node=alice, name="br0")
        )
        bob_eth0 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth0")
        )
        bob_eth1 = get_one(
            PhysicalInterface.objects.filter(node=bob, name="eth1")
        )
        # Registration with beaconing; we should see all these interfaces
        # appear on the same VLAN.
        self.assertEqual(alice_br0.vlan, bob_eth0.vlan)
        self.assertEqual(bob_eth1.vlan, bob_eth0.vlan)
