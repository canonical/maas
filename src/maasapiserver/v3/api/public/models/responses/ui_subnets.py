#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    BaseHrefWithId,
    HalResponse,
    PaginatedResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.models.fields import IPv4v6Network
from maasservicelayer.models.ui_subnets import UISubnet


class VlanHref(BaseHrefWithId):
    vid: str


class UISubnetResponse(HalResponse[BaseHal]):
    kind = "UISubnet"
    id: int
    name: Optional[str]
    description: Optional[str]
    cidr: IPv4v6Network
    rdns_mode: RdnsMode
    gateway_ip: Optional[IPvAnyAddress]
    dns_servers: Optional[list[str]]
    allow_dns: bool
    allow_proxy: bool
    active_discovery: bool
    managed: bool
    disabled_boot_architectures: list[str]

    @classmethod
    def from_model(cls, subnet: UISubnet, self_base_hyperlink: str) -> Self:
        return cls(
            id=subnet.id,
            name=subnet.name,
            description=subnet.description,
            cidr=subnet.cidr,
            rdns_mode=subnet.rdns_mode,
            gateway_ip=subnet.gateway_ip,
            dns_servers=subnet.dns_servers,
            allow_dns=subnet.allow_dns,
            allow_proxy=subnet.allow_proxy,
            active_discovery=subnet.active_discovery,
            managed=subnet.managed,
            disabled_boot_architectures=subnet.disabled_boot_architectures,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{subnet.id}"
                )
            ),
            hal_embedded={  # pyright: ignore [reportCallIssue]
                "fabric": BaseHrefWithId(
                    href=f"{V3_API_PREFIX}/fabrics/{subnet.fabric_id}",
                    id=str(subnet.fabric_id),
                    name=subnet.fabric_name,
                ),
                "vlan": VlanHref(
                    href=f"{V3_API_PREFIX}/fabrics/{subnet.fabric_id}/vlans/{subnet.vlan_id}",
                    id=str(subnet.vlan_id),
                    vid=str(subnet.vlan_vid),
                ),
                "space": BaseHrefWithId(
                    href=f"{V3_API_PREFIX}/spaces/{subnet.space_id}",
                    id=str(subnet.space_id),
                    name=subnet.space_name,
                )
                if subnet.space_id is not None
                else {},
            },
        )


class UISubnetsListResponse(PaginatedResponse[UISubnetResponse]):
    kind = "UISubnetsList"
