from enum import Enum
from typing import Optional

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    TokenPaginatedResponse,
)
from maasserver.enum import NODE_STATUS_CHOICES
from metadataserver.enum import HARDWARE_TYPE_CHOICES
from provisioningserver.drivers.pod.lxd import LXDPodDriver
from provisioningserver.drivers.pod.virsh import VirshPodDriver
from provisioningserver.drivers.power.registry import power_drivers

MachineStatusEnum = Enum(
    "MachineStatus",
    dict({str(name).lower(): int(code) for code, name in NODE_STATUS_CHOICES}),
)
PowerTypeEnum = Enum(
    "PowerType",
    dict(
        {
            str(driver.name).lower(): str(driver.name).lower()
            for driver in power_drivers + [LXDPodDriver(), VirshPodDriver()]
        }
    ),
)

HardwareDeviceTypeEnum = Enum(
    "HardwareDeviceType",
    dict(
        {str(name).lower(): int(code) for code, name in HARDWARE_TYPE_CHOICES}
    ),
)


class MachineResponse(HalResponse[BaseHal]):
    kind = "Machine"
    id: int
    system_id: str
    description: str
    owner: Optional[str]
    cpu_speed_MHz: int
    memory_MiB: int
    osystem: str
    architecture: Optional[str]
    distro_series: str
    hwe_kernel: Optional[str]
    locked: bool
    cpu_count: int
    status: MachineStatusEnum
    power_type: Optional[PowerTypeEnum]
    fqdn: str


class MachinesListResponse(TokenPaginatedResponse[MachineResponse]):
    kind = "MachinesList"


class UsbDeviceResponse(HalResponse[BaseHal]):
    kind = "MachineHardwareDevice"
    id: int
    type: HardwareDeviceTypeEnum
    vendor_id: str
    product_id: str
    vendor_name: str
    product_name: str
    commissioning_driver: str
    bus_number: int
    device_number: int


class UsbDevicesListResponse(TokenPaginatedResponse[UsbDeviceResponse]):
    kind = "MachineHardwareDevicesList"


class PciDeviceResponse(HalResponse[BaseHal]):
    kind = "MachinePciDevice"
    id: int
    type: HardwareDeviceTypeEnum
    vendor_id: str
    product_id: str
    vendor_name: str
    product_name: str
    commissioning_driver: str
    bus_number: int
    device_number: int
    pci_address: str


class PciDevicesListResponse(TokenPaginatedResponse[UsbDeviceResponse]):
    kind = "MachinePciDevicesList"
