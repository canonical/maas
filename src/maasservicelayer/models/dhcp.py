# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass


@dataclass
class VlanData:
    id: int
    vid: int
    relayed_vlan_id: int | None
    mtu: int


@dataclass
class InterfaceData:
    id: int
    vlan_id: int
    name: str


@dataclass
class IPRangeData:
    id: int
    subnet_id: int
    dynamic: bool
    start_ip: str
    end_ip: str


@dataclass
class HostReservationData:
    ip: str
    mac_address: str
    hostname: str


@dataclass
class SubnetData:
    id: int
    rack_system_id: str
    secondary_rack_system_id: str | None
    ip_version: int
    cidr: str
    gateway_ip: str
    dns_servers: list[str]
    allow_dns: bool
    vlan_id: int
    vlan_mtu: int
    mask: str
    broadcast_ip: str
    domain_name: str
    search_list: list[str]
    ntp_servers: list[str]
    next_server: str
    pools: list[IPRangeData]
    host_reservations: list[HostReservationData]


@dataclass(frozen=True)
class KeaHAConfig:
    primary_rack_system_id: str
    secondary_rack_system_id: str
    primary_rack_ip: str
    secondary_rack_ip: str


@dataclass
class DHCPDataForAgent:
    vlans: list[VlanData]
    subnets: list[SubnetData]
    ipranges: list[IPRangeData]
    interfaces: list[InterfaceData]
    default_dns_servers: list[str]
    ntp_servers: list[str]
    ha_data: list[KeaHAConfig]
