# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re
from typing import Optional

from pydantic import validator

from maascommon.enums.node import HardwareDeviceTypeEnum
from maasservicelayer.enums.power_drivers import PowerTypeEnum
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.nodes import Node

# PCIE and USB vendor and product ids are represented as a 2 byte hex string
DEVICE_ID_REGEX = re.compile(r"^[\da-f]{4}$", re.I)


@generate_builder()
class Machine(Node):
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
    power_type: Optional[PowerTypeEnum]
    fqdn: str
    hostname: str


class HardwareDevice(MaasTimestampedBaseModel):
    hardware_type: HardwareDeviceTypeEnum = HardwareDeviceTypeEnum.NODE
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


@generate_builder()
class UsbDevice(HardwareDevice):
    pass


@generate_builder()
class PciDevice(HardwareDevice):
    pci_address: str
