# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.vlans import Vlan


@dataclass(frozen=True)
class WithSystemId(CustomFilter):
    model: ClassVar = Vlan
    system_id: str


@dataclass(frozen=True)
class WithNodeType(CustomFilter):
    model: ClassVar = Vlan
    node_type: NodeTypeEnum


@dataclass(frozen=True)
class WithPrimaryOrSecondaryRackId(CustomFilter):
    model: ClassVar = Vlan
    rack_id: int


@dataclass(frozen=True)
class WithRelayVlanExists(CustomFilter):
    model: ClassVar = Vlan
    exists: bool


class VlansFilters(FilterFactory):
    model = Vlan

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> FieldFilter:
        return cls._equals("fabric_id", fabric_id)

    @classmethod
    def with_space_id(cls, space_id: int) -> FieldFilter:
        return cls._equals("space_id", space_id)

    @classmethod
    def with_system_id(cls, system_id: str) -> WithSystemId:
        return WithSystemId(system_id)

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> WithNodeType:
        return WithNodeType(type)

    @classmethod
    def with_dhcp_on(cls, on: bool) -> FieldFilter:
        return cls._equals("dhcp_on", on)

    @classmethod
    def with_primary_or_secondary_rack_id(
        cls, rack_id: int
    ) -> WithPrimaryOrSecondaryRackId:
        return WithPrimaryOrSecondaryRackId(rack_id)

    @classmethod
    def with_relay_vlan_id(cls, relay_vlan_id: int) -> FieldFilter:
        return cls._equals("relay_vlan_id", relay_vlan_id)

    @classmethod
    def with_relay_vlan_id_in(cls, relay_vlan_ids: list[int]) -> FieldFilter:
        return cls._is_in("relay_vlan_id", relay_vlan_ids)

    @classmethod
    def with_relay_vlan_exists(cls, exists: bool) -> WithRelayVlanExists:
        return WithRelayVlanExists(exists)
