# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

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
    name: Optional[str] = None
    description: Optional[str] = None
    cidr: IPv4v6Network
    rdns_mode: RdnsMode
    gateway_ip: Optional[IPvAnyAddress] = None
    dns_servers: Optional[list[str]] = None
    allow_dns: bool
    allow_proxy: bool
    active_discovery: bool
    managed: bool
    disabled_boot_architectures: list[str]
    vlan_id: int
    vlan_vid: int
    vlan_name: Optional[str] = None
    vlan_dhcp_on: bool
    vlan_external_dhcp: Optional[IPvAnyAddress] = None
    vlan_relay_vlan_id: Optional[int] = None
    fabric_id: int
    fabric_name: Optional[str] = None
    space_id: Optional[int] = None
    space_name: Optional[str] = None
    statistics: Optional[UISubnetStatistics] = None
