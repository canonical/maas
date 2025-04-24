# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.fields import IPv4v6Network, MacAddress


class Discovery(MaasBaseModel):
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
    subnet_prefixlen: int | None
