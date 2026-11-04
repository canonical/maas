# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.fields import IPv4v6Network
from maasservicelayer.models.subnets import Subnet


@dataclass(frozen=True)
class SubnetFabricFilter(CustomFilter):
    model: ClassVar = Subnet
    fabric_id: int


@dataclass(frozen=True)
class SubnetRdnsModeNotFilter(CustomFilter):
    model: ClassVar = Subnet
    rdns_mode: RdnsMode


@dataclass(frozen=True)
class SubnetCIDROverlapFilter(CustomFilter):
    model: ClassVar = Subnet
    cidr: IPv4v6Network


class SubnetFilters(FilterFactory):
    model = Subnet

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> FieldFilter:
        return cls._equals("vlan_id", vlan_id)

    @classmethod
    def with_vlan_id_in(cls, vlan_ids: list[int]) -> FieldFilter:
        return cls._is_in("vlan_id", vlan_ids)

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> SubnetFabricFilter:
        return SubnetFabricFilter(fabric_id)

    @classmethod
    def with_allow_dns(cls, allow_dns: bool) -> FieldFilter:
        return cls._equals("allow_dns", allow_dns)

    @classmethod
    def with_managed(cls, managed: bool) -> FieldFilter:
        return cls._equals("managed", managed)

    @classmethod
    def with_rdns_mode(cls, rdns_mode: RdnsMode) -> FieldFilter:
        return cls._equals("rdns_mode", rdns_mode)

    @classmethod
    def with_not_rdns_mode(
        cls, rdns_mode: RdnsMode
    ) -> SubnetRdnsModeNotFilter:
        return SubnetRdnsModeNotFilter(rdns_mode)

    @classmethod
    def with_cidr_overlap(cls, cidr: IPv4v6Network) -> SubnetCIDROverlapFilter:
        return SubnetCIDROverlapFilter(cidr)
