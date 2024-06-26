from enum import Enum
from ipaddress import IPv4Address, IPv6Address
from typing import Optional, Union

from pydantic import BaseModel, Field

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    TokenPaginatedResponse,
)
from maasserver.enum import INTERFACE_LINK_TYPE_CHOICES, INTERFACE_TYPE_CHOICES

InterfaceTypeEnum = Enum(
    "InterfaceType",
    dict({str(name).lower(): str(name) for name, _ in INTERFACE_TYPE_CHOICES}),
)
LinkModeEnum = Enum(
    "IpMode",
    dict({str(name): str(name) for name, _ in INTERFACE_LINK_TYPE_CHOICES}),
)

IpAddress = Union[IPv4Address, IPv6Address]


class LinkResponse(BaseModel):
    id: int
    mode: LinkModeEnum
    ip_address: Optional[IpAddress]


class InterfaceResponse(HalResponse[BaseHal]):
    kind = "Interface"
    id: int
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
    links: list[LinkResponse] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class InterfaceListResponse(TokenPaginatedResponse[InterfaceResponse]):
    kind = "InterfaceList"
