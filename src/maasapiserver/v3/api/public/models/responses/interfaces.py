# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import BaseModel, Field, IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maascommon.enums.interface import InterfaceLinkType
from maasservicelayer.models.interfaces import Interface, InterfaceType, Link


class LinkResponse(BaseModel):
    id: int
    mode: InterfaceLinkType
    ip_address: Optional[IPvAnyAddress]

    @classmethod
    def from_model(cls, link: Link) -> "LinkResponse":
        return cls(id=link.id, mode=link.mode, ip_address=link.ip_address)


class InterfaceResponse(HalResponse[BaseHal]):
    kind = "Interface"
    id: int
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
    links: list[LinkResponse] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_model(
        cls, interface: Interface, self_base_hyperlink: str
    ) -> "InterfaceResponse":
        return cls(
            id=interface.id,
            name=interface.name,
            type=interface.type,
            mac_address=interface.mac_address,
            # TODO
            # effective_mtu=interface.effective_mtu,
            link_connected=interface.link_connected,
            interface_speed=interface.interface_speed,
            enabled=interface.enabled,
            link_speed=interface.link_speed,
            sriov_max_vf=interface.sriov_max_vf,
            links=[LinkResponse.from_model(link) for link in interface.links],
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{interface.id}"
                )
            ),
        )


class InterfaceListResponse(TokenPaginatedResponse[InterfaceResponse]):
    kind = "InterfaceList"
