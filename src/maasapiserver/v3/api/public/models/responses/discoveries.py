# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Self

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.models.fields import IPv4v6Network, MacAddress


class DiscoveryResponse(HalResponse[BaseHal]):
    kind = "Discovery"
    id: int
    discovery_id: str | None
    neighbour_id: int | None
    ip: IPvAnyAddress | None
    mac_address: MacAddress | None
    vid: int | None
    first_seen: datetime | None
    last_seen: datetime | None
    mdns_id: int | None
    hostname: str | None
    observer_id: int | None
    observer_system_id: str | None
    observer_hostname: str | None
    observer_interface_id: int | None
    observer_interface_name: str | None
    fabric_id: int | None
    fabric_name: str | None
    vlan_id: int | None
    is_external_dhcp: bool | None
    subnet_id: int | None
    subnet_cidr: IPv4v6Network | None

    @classmethod
    def from_model(
        cls, discovery: Discovery, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=discovery.id,
            discovery_id=discovery.discovery_id,
            neighbour_id=discovery.neighbour_id,
            ip=discovery.ip,
            mac_address=discovery.mac_address,
            vid=discovery.vid,
            first_seen=discovery.first_seen,
            last_seen=discovery.last_seen,
            mdns_id=discovery.mdns_id,
            hostname=discovery.hostname,
            observer_id=discovery.observer_id,
            observer_system_id=discovery.observer_system_id,
            observer_hostname=discovery.observer_hostname,
            observer_interface_id=discovery.observer_interface_id,
            observer_interface_name=discovery.observer_interface_name,
            fabric_id=discovery.fabric_id,
            fabric_name=discovery.fabric_name,
            vlan_id=discovery.vlan_id,
            is_external_dhcp=discovery.is_external_dhcp,
            subnet_id=discovery.subnet_id,
            subnet_cidr=discovery.subnet_cidr,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{discovery.id}"
                )
            ),
        )


class DiscoveriesListResponse(PaginatedResponse[DiscoveryResponse]):
    kind = "DiscoveriesList"
