# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.fields import IPv4v6Network, MacAddress


class Discovery(MaasBaseModel):
    discovery_id: str | None = None
    neighbour_id: int | None = None
    ip: IPvAnyAddress | None = None
    mac_address: MacAddress | None = None
    vid: int | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    mdns_id: int | None = None
    hostname: str | None = None
    observer_id: int | None = None
    observer_system_id: str | None = None
    observer_hostname: str | None = None
    observer_interface_id: int | None = None
    observer_interface_name: str | None = None
    fabric_id: int | None = None
    fabric_name: str | None = None
    vlan_id: int | None = None
    is_external_dhcp: bool | None = None
    subnet_id: int | None = None
    subnet_cidr: IPv4v6Network | None = None
    subnet_prefixlen: int | None = None
