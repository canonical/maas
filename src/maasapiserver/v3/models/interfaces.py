from typing import Optional

from pydantic import BaseModel, Field

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.interfaces import (
    InterfaceResponse,
    InterfaceTypeEnum,
    IpAddress,
    LinkModeEnum,
    LinkResponse,
)
from maasapiserver.v3.models.base import MaasTimestampedBaseModel
from maasserver.enum import INTERFACE_LINK_TYPE, IPADDRESS_TYPE


class Link(BaseModel):
    id: int
    ip_type: int
    ip_address: Optional[IpAddress]
    ip_subnet: int

    # derived from StaticIPAddress.get_interface_link_type
    @property
    def mode(self) -> LinkModeEnum:
        match self.ip_type:
            case IPADDRESS_TYPE.AUTO:
                mode = INTERFACE_LINK_TYPE.AUTO
            case IPADDRESS_TYPE.STICKY:
                mode = (
                    INTERFACE_LINK_TYPE.STATIC
                    if self.ip_address is None
                    else INTERFACE_LINK_TYPE.LINK_UP
                )
            case IPADDRESS_TYPE.USER_RESERVED:
                mode = INTERFACE_LINK_TYPE.STATIC
            case IPADDRESS_TYPE.DHCP:
                mode = INTERFACE_LINK_TYPE.DHCP
            case IPADDRESS_TYPE.DISCOVERED:
                mode = INTERFACE_LINK_TYPE.DHCP
        return LinkModeEnum(mode)

    class Config:
        arbitrary_types_allowed = True

    def to_response(self) -> LinkResponse:
        return LinkResponse(
            id=self.id, mode=self.mode, ip_address=self.ip_address
        )


class Interface(MaasTimestampedBaseModel):
    name: str
    type: InterfaceTypeEnum
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

    def to_response(self, self_base_hyperlink: str) -> InterfaceResponse:
        return InterfaceResponse(
            id=self.id,
            name=self.name,
            type=self.type,
            mac_address=self.mac_address,
            # TODO
            # effective_mtu=self.effective_mtu,
            link_connected=self.link_connected,
            interface_speed=self.interface_speed,
            enabled=self.enabled,
            link_speed=self.link_speed,
            sriov_max_vf=self.sriov_max_vf,
            links=[link.to_response() for link in self.links],
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
