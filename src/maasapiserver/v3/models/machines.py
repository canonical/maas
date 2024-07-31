from typing import Optional

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.machines import (
    HardwareDeviceTypeEnum,
    MachineResponse,
    MachineStatusEnum,
    PowerTypeEnum,
    UsbDeviceResponse,
)
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


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
    vendor_id: int
    # TODO: add validator?
    product_id: int
    vendor_name: str
    product_name: str
    commissioning_driver: str
    bus_number: int
    device_number: int
    # numa_node_id: int
    # physical_interface_id: Optional[int]
    # physical_blockdevice_id: Optional[int]
    # node_config_id: int


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
