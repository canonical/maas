import re
from typing import Optional

from pydantic import validator

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.machines import (
    HardwareDeviceTypeEnum,
    MachineResponse,
    MachineStatusEnum,
    PciDeviceResponse,
    PowerTypeEnum,
    UsbDeviceResponse,
)
from maasapiserver.v3.models.base import MaasTimestampedBaseModel

# PCIE and USB vendor and product ids are represented as a 2 byte hex string
DEVICE_ID_REGEX = re.compile(r"^[\da-f]{4}$", re.I)


class Machine(MaasTimestampedBaseModel):
    system_id: str
    description: str
    owner: Optional[str]
    cpu_speed: int
    memory: int
    osystem: str
    architecture: Optional[str]
    distro_series: str
    hwe_kernel: Optional[str]
    locked: bool
    cpu_count: int
    status: MachineStatusEnum
    power_type: Optional[PowerTypeEnum]
    fqdn: str
    hostname: str

    def to_response(self, self_base_hyperlink: str) -> MachineResponse:
        return MachineResponse(
            id=self.id,
            system_id=self.system_id,
            description=self.description,
            owner=self.owner,
            cpu_speed_MHz=self.cpu_speed,
            memory_MiB=self.memory,
            osystem=self.osystem,
            architecture=self.architecture,
            distro_series=self.distro_series,
            hwe_kernel=self.hwe_kernel,
            locked=self.locked,
            cpu_count=self.cpu_count,
            status=self.status,
            power_type=self.power_type,
            fqdn=self.fqdn,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )


class HardwareDevice(MaasTimestampedBaseModel):
    # TODO: move HARDWARE_TYPE to enum and change the type here
    hardware_type: HardwareDeviceTypeEnum = HardwareDeviceTypeEnum.node
    vendor_id: str
    product_id: str
    vendor_name: str
    product_name: str
    commissioning_driver: str
    bus_number: int
    device_number: int
    # numa_node_id: int
    # physical_interface_id: Optional[int]
    # physical_blockdevice_id: Optional[int]
    # node_config_id: int

    @validator("vendor_id", "product_id")
    def validate_hex_ids(cls, id):
        if not DEVICE_ID_REGEX.match(id):
            raise ValueError("Must be an 8 byte hex value")
        return id


class UsbDevice(HardwareDevice):

    def to_response(self, self_base_hyperlink: str) -> UsbDeviceResponse:
        return UsbDeviceResponse(
            id=self.id,
            type=self.hardware_type,
            vendor_id=self.vendor_id,
            product_id=self.product_id,
            vendor_name=self.vendor_name,
            product_name=self.product_name,
            commissioning_driver=self.commissioning_driver,
            bus_number=self.bus_number,
            device_number=self.device_number,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )


class PciDevice(HardwareDevice):
    pci_address: str

    def to_response(self, self_base_hyperlink: str) -> PciDeviceResponse:
        return PciDeviceResponse(
            id=self.id,
            type=self.hardware_type,
            vendor_id=self.vendor_id,
            product_id=self.product_id,
            vendor_name=self.vendor_name,
            product_name=self.product_name,
            commissioning_driver=self.commissioning_driver,
            bus_number=self.bus_number,
            device_number=self.device_number,
            pci_address=self.pci_address,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
