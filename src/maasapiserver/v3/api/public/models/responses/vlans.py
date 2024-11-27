#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.vlans import Vlan


class VlanResponse(HalResponse[BaseHal]):
    kind = "Vlan"
    id: int
    vid: int
    name: Optional[str]
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: Optional[str]
    primary_rack: Optional[int]
    secondary_rack: Optional[int]
    relay_vlan_id: Optional[int]
    space: Optional[BaseHref]

    @classmethod
    def from_model(
        cls, vlan: Vlan, self_base_hyperlink: str
    ) -> "VlanResponse":
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
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{vlan.id}"
                )
            ),
        )


class VlansListResponse(TokenPaginatedResponse[VlanResponse]):
    kind = "VlansList"
