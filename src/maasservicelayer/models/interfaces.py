# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import BaseModel, Field, IPvAnyAddress

from maascommon.enums.interface import InterfaceLinkType, InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.models.base import MaasTimestampedBaseModel


class Link(BaseModel):
    id: int
    ip_type: int
    ip_address: Optional[IPvAnyAddress]
    ip_subnet: int

    # derived from StaticIPAddress.get_interface_link_type
    @property
    def mode(self) -> InterfaceLinkType:
        match self.ip_type:
            case IpAddressType.AUTO:
                mode = InterfaceLinkType.AUTO
            case IpAddressType.STICKY:
                mode = (
                    InterfaceLinkType.STATIC
                    if self.ip_address is None
                    else InterfaceLinkType.LINK_UP
                )
            case IpAddressType.USER_RESERVED:
                mode = InterfaceLinkType.STATIC
            case IpAddressType.DHCP:
                mode = InterfaceLinkType.DHCP
            case IpAddressType.DISCOVERED:
                mode = InterfaceLinkType.DHCP
        return mode

    class Config:
        arbitrary_types_allowed = True


class Interface(MaasTimestampedBaseModel):
    name: str
    type: InterfaceType
    mac_address: Optional[str]
    # TODO
    # effective_mtu: int = 0
    link_connected: bool = True
    interface_speed: int = 0
    enabled: bool = True
    link_speed: int = 0
    sriov_max_vf: int = 0
    links: list[Link] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
