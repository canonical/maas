# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.vlans import VlanResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Vlan(MaasTimestampedBaseModel):
    id: int
    vid: int
    name: Optional[str]
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: Optional[str]
    primary_rack_id: Optional[str]
    secondary_rack_id: Optional[str]
    relay_vlan: Optional[int]
    fabric_id: int
    space_id: Optional[int]

    def to_response(self, self_base_hyperlink: str) -> VlanResponse:
        return VlanResponse(
            id=self.id,
            vid=self.vid,
            name=self.name,
            description=self.description,
            mtu=self.mtu,
            dhcp_on=self.dhcp_on,
            external_dhcp=self.external_dhcp,
            primary_rack=self.primary_rack_id,
            secondary_rack=self.secondary_rack_id,
            relay_vlan=self.relay_vlan,
            fabric=BaseHref(href=f"{V3_API_PREFIX}/fabrics/{self.fabric_id}"),
            space=(
                BaseHref(href=f"{V3_API_PREFIX}/spaces/{self.space_id}")
                if self.space_id
                else None
            ),
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
