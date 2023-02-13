from copy import deepcopy
import dataclasses
from enum import Enum
import random
from typing import Dict, List, Optional

from maasserver.testing.factory import factory
from provisioningserver.utils import kernel_to_debian_architecture
from provisioningserver.utils.network import (
    annotate_with_default_monitored_interfaces,
    get_default_monitored_interfaces,
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
        default_factory=lambda: ["fiber"]
    )
    port_type: str = "fiber"
    transceiver_type: str = "internal"
    auto_negotiation: bool = True
    link_detected: bool = True
    link_speed: int = 10000
    link_duplex: str = "full"


class DeviceType(Enum):
    PCI = 1
    USB = 2


@dataclasses.dataclass
class LXDNetworkCard:
    pci_address: Optional[str] = None
    usb_address: Optional[str] = None
    vendor: str = "My Corporation"
    vendor_id: str = "1234"
    product: str = "My Gigabit Network Connection"
    product_id: str = "5678"
    firmware_version: str = "1.63, 0x800009fa"
    numa_node: int = 0
    driver: str = "mydriver"
    driver_version: str = "1.2.3"
    ports: Optional[List[LXDNetworkPort]] = None


@dataclasses.dataclass
class LXDPCIDeviceVPD:
    entries: Dict[str, str]
    product_name: str = "My PCI Device"


@dataclasses.dataclass
class LXDPCIDevice:
    pci_address: str
    vendor_id: str
    vendor: str
    product_id: str
    product: str
    driver: str
    driver_version: str
    vpd: Optional[LXDPCIDeviceVPD] = None


@dataclasses.dataclass
class LXDUSBDevice:
    bus_address: int
    device_address: int
    vendor_id: str
    vendor: str
    product_id: str
    product: str
    driver: str
    driver_version: str


@dataclasses.dataclass
class LXDSystem:
    family: str = ""


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
        server_name=None,
        kernel_architecture="x86_64",
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
        if server_name is None:
            factory.make_name("host")
        self.environment = {
            "kernel": "Linux",
            "kernel_architecture": kernel_architecture,
            "kernel_version": "5.4.0-67-generic",
            "os_name": "ubuntu",
            "os_version": "20.04",
            "server": "maas-machine-resources",
            "server_name": server_name,
            "server_version": "4.11",
        }
        self.address_annotations = {}
        self._allocated_pci_addresses = []
        self._pci_devices = []
        self._allocated_usb_addresses = []
        self._usb_devices = []
        self.networks = {}
        self._network_cards = []
        self._boot_interface_mac = None
        if disks is None:
            disks = [LXDDisk("sda")]
        self._disks = list(disks)
        self.hints = None
        self.storage_extra = None
        self._system_resource = LXDSystem()

    @property
    def debian_architecture(self):
        return kernel_to_debian_architecture(
            self.environment["kernel_architecture"]
        )

    def add_disk(self, id: str, size: int):
        self._disks.append(LXDDisk(id, size=size))

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

    def allocate_usb_address(self):
        prev_address = (
            self._allocated_usb_addresses[-1]
            if self._allocated_usb_addresses
            else "0:0"
        )
        bus, device = prev_address.split(":")
        next_device = int(device, 16) + 1
        self._allocated_usb_addresses.append(f"{bus}:{next_device:0>1x}")
        return self._allocated_usb_addresses[-1]

    def get_available_vid(self):
        available_vids = set(range(2, 4095))
        used_vids = {
            network.vlan.vid
            for network in self.networks.values()
            if network.vlan is not None
        }
        available_vids = list(available_vids.difference(used_vids))
        return random.choice(available_vids)

    def create_network_card(self, device_type=DeviceType.PCI):
        card = None
        if device_type == DeviceType.PCI:
            addr = self.allocate_pci_address()
            card = LXDNetworkCard(pci_address=addr)
            self.create_pci_device(
                addr,
                card.vendor_id,
                card.vendor,
                card.product_id,
                card.product,
                card.driver,
                card.driver_version,
            )
        if device_type == DeviceType.USB:
            addr = self.allocate_usb_address()
            card = LXDNetworkCard(usb_address=addr)
            self.create_usb_device(
                addr,
                card.vendor_id,
                card.vendor,
                card.product_id,
                card.product,
                card.driver,
                card.driver_version,
            )
        self._network_cards.append(card)
        return card

    def create_pci_device(
        self,
        addr,
        vendor_id,
        vendor,
        product_id,
        product,
        driver,
        driver_version,
        vpd={},
    ):
        device = LXDPCIDevice(
            addr,
            vendor_id,
            vendor,
            product_id,
            product,
            driver,
            driver_version,
            vpd,
        )
        self._pci_devices.append(device)

    def create_usb_device(
        self,
        addr,
        vendor_id,
        vendor,
        product_id,
        product,
        driver,
        driver_version,
    ):
        bus, device = addr.split(":")
        device = LXDUSBDevice(
            bus,
            device,
            vendor_id,
            vendor,
            product_id,
            product,
            driver,
            driver_version,
        )
        self._usb_devices.append(device)

    def create_physical_network(
        self,
        name=None,
        mac_address=None,
        card=None,
        port=None,
    ):
        if card is None:
            card = self.create_network_card()
        if card.ports is None:
            card.ports = []
        network = self.create_physical_network_without_nic(name, mac_address)
        if port is None:
            port = LXDNetworkPort(
                network.name, len(card.ports), address=network.hwaddr
            )
        card.ports.append(port)
        if self._boot_interface_mac is None:
            self._boot_interface_mac = network.hwaddr
        return network

    def create_physical_network_without_nic(
        self,
        name=None,
        mac_address=None,
    ):
        if name is None:
            name = factory.make_name("eth")
        if mac_address is None:
            mac_address = factory.make_mac_address()
        network = LXDNetwork(name, mac_address)
        self.networks[name] = network
        return network

    def create_vlan_network(
        self,
        name=None,
        vid=None,
        mac_address=None,
        parent=None,
    ):
        if name is None:
            name = factory.make_name("vlan")
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
            name = factory.make_name("bridge")
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
            name = factory.make_name("bond")
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

    def create_system_resource(self, family):
        system = LXDSystem(family)
        self._system_resource = system
        return system

    def render(self, include_extra=False):
        storage_resources = {
            "disks": [dataclasses.asdict(disk) for disk in self._disks],
            "total": len(self._disks),
        }
        network_resources = {
            "cards": [
                dataclasses.asdict(
                    card,
                    # Network card can have pci_address or usb_address.
                    # The one that is not set will be rendered as None,
                    # but machine-resources has omitempty JSON tag,
                    # thus it will not have empty property, and we want to be compliant
                    dict_factory=lambda x: {
                        k: v
                        for (k, v) in x
                        if not (
                            k in ("pci_address", "usb_address") and v is None
                        )
                    },
                )
                for card in self._network_cards
            ],
            "total": len(self._network_cards),
        }
        for card in network_resources["cards"]:
            if card["ports"] is None:
                del card["ports"]
        networks = {
            name: dataclasses.asdict(network)
            for name, network in self.networks.items()
        }
        pci_resources = {
            "devices": [
                dataclasses.asdict(device) for device in self._pci_devices
            ],
            "total": len(self._pci_devices),
        }
        usb_resources = {
            "devices": [
                dataclasses.asdict(device) for device in self._usb_devices
            ],
            "total": len(self._usb_devices),
        }

        old_interfaces_data = self._generate_interfaces()
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
                "usb": usb_resources,
                "pci": pci_resources,
                "system": dataclasses.asdict(self._system_resource),
            },
            "networks": networks,
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
        if include_extra:
            data["network-extra"] = {
                "interfaces": old_interfaces_data,
                "monitored-interfaces": get_default_monitored_interfaces(
                    old_interfaces_data
                ),
                "hints": self.hints,
            }
        if self.storage_extra:
            data["storage-extra"] = deepcopy(self.storage_extra)
        return data

    def render_kernel_cmdline(self):
        """Return the kernel command line, including the BOOTIF."""
        cmdline = "console=tty1 console=ttyS0"
        if self._boot_interface_mac:
            cmdline += f"{cmdline} BOOTIF=01-{self._boot_interface_mac}"
        return cmdline

    def _generate_interfaces(self):
        # XXX: It would be good if this method could basically call
        # get_all_interfaces_definition(), passing in information it
        # needs. But considering the goal is to minimize information and
        # instead make use of the LXD data directly, it's probably worth
        # holding off until there's less information to render.
        interfaces = {}
        for name, network in self.networks.items():
            if network.type != "broadcast":
                continue
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
            if not card.ports:
                continue
            for port in card.ports:
                if port.id == port_name:
                    return port.address

        return default
