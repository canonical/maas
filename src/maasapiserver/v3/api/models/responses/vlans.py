#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)


class VlanResponse(HalResponse[BaseHal]):
    kind = "Vlan"
    id: int
    vid: int
    name: Optional[str]
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: Optional[str]
    primary_rack: Optional[str]
    secondary_rack: Optional[str]
    relay_vlan: Optional[int]
    fabric: BaseHref
    space: Optional[BaseHref]


class VlansListResponse(TokenPaginatedResponse[VlanResponse]):
    kind = "VlansList"
