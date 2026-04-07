# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, IPvAnyAddress

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.models.base import MaasTimestampedBaseModel
from maasservicelayer.models.fields import IPv4v6Network


class UISubnetStatistics(BaseModel):
    num_available: int
    largest_available: int
    num_unavailable: int
    total_addresses: int
    usage: float
    usage_string: str
    available_string: str
    first_address: str
    last_address: str
    ip_version: int


class UISubnet(MaasTimestampedBaseModel):
    name: str | None = None
    description: str | None = None
    cidr: IPv4v6Network
    rdns_mode: RdnsMode
    gateway_ip: IPvAnyAddress | None = None
    dns_servers: list[str] | None = None
    allow_dns: bool
    allow_proxy: bool
    active_discovery: bool
    managed: bool
    disabled_boot_architectures: list[str]
    vlan_id: int
    vlan_vid: int
    vlan_name: str | None = None
    vlan_dhcp_on: bool
    vlan_external_dhcp: IPvAnyAddress | None = None
    vlan_relay_vlan_id: int | None = None
    fabric_id: int
    fabric_name: str | None = None
    space_id: int | None = None
    space_name: str | None = None
    statistics: UISubnetStatistics | None = None
