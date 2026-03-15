#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field, IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.vlans import Vlan


class VlanResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Vlan")
    id: int
    vid: int
    name: str | None = None
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: IPvAnyAddress | None = None
    primary_rack: int | None = None
    secondary_rack: int | None = None
    relay_vlan_id: int | None = None
    space: BaseHref | None = None

    @classmethod
    def from_model(cls, vlan: Vlan, self_base_hyperlink: str) -> Self:
        return cls(
            id=vlan.id,
            vid=vlan.vid,
            name=vlan.name,
            description=vlan.description,
            mtu=vlan.mtu,
            dhcp_on=vlan.dhcp_on,
            external_dhcp=vlan.external_dhcp,
            primary_rack=vlan.primary_rack_id,
            secondary_rack=vlan.secondary_rack_id,
            relay_vlan_id=vlan.relay_vlan_id,
            space=(
                BaseHref(href=f"{V3_API_PREFIX}/spaces/{vlan.space_id}")
                if vlan.space_id
                else None
            ),
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{vlan.id}"
                )
            ),
        )


class VlansListResponse(PaginatedResponse[VlanResponse]):
    kind: str = Field(default="VlansList")
