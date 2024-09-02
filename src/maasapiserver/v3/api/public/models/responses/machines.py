# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maasservicelayer.models.machines import (
    HardwareDeviceTypeEnum,
    Machine,
    MachineStatusEnum,
    PciDevice,
    PowerTypeEnum,
    UsbDevice,
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

    @classmethod
    def from_model(
        cls, machine: Machine, self_base_hyperlink: str
    ) -> "MachineResponse":
        return cls(
            id=machine.id,
            system_id=machine.system_id,
            description=machine.description,
            owner=machine.owner,
            cpu_speed_MHz=machine.cpu_speed,
            memory_MiB=machine.memory,
            osystem=machine.osystem,
            architecture=machine.architecture,
            distro_series=machine.distro_series,
            hwe_kernel=machine.hwe_kernel,
            locked=machine.locked,
            cpu_count=machine.cpu_count,
            status=machine.status,
            power_type=machine.power_type,
            fqdn=machine.fqdn,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{machine.id}"
                )
            ),
        )


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

    @classmethod
    def from_model(
        cls, usb_device: UsbDevice, self_base_hyperlink: str
    ) -> "UsbDeviceResponse":
        return cls(
            id=usb_device.id,
            type=usb_device.hardware_type,
            vendor_id=usb_device.vendor_id,
            product_id=usb_device.product_id,
            vendor_name=usb_device.vendor_name,
            product_name=usb_device.product_name,
            commissioning_driver=usb_device.commissioning_driver,
            bus_number=usb_device.bus_number,
            device_number=usb_device.device_number,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{usb_device.id}"
                )
            ),
        )


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

    @classmethod
    def from_model(
        cls, pci_device: PciDevice, self_base_hyperlink: str
    ) -> "PciDeviceResponse":
        return cls(
            id=pci_device.id,
            type=pci_device.hardware_type,
            vendor_id=pci_device.vendor_id,
            product_id=pci_device.product_id,
            vendor_name=pci_device.vendor_name,
            product_name=pci_device.product_name,
            commissioning_driver=pci_device.commissioning_driver,
            bus_number=pci_device.bus_number,
            device_number=pci_device.device_number,
            pci_address=pci_device.pci_address,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{pci_device.id}"
                )
            ),
        )


class PciDevicesListResponse(TokenPaginatedResponse[UsbDeviceResponse]):
    kind = "MachinePciDevicesList"
