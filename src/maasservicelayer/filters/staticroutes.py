# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.staticroutes import StaticRoute


@dataclass(frozen=True)
class WithVlanId(CustomFilter):
    model: ClassVar = StaticRoute
    vlan_id: int


@dataclass(frozen=True)
class WithFabricId(CustomFilter):
    model: ClassVar = StaticRoute
    fabric_id: int


class StaticRoutesFilters(FilterFactory):
    model = StaticRoute

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_source_id(cls, subnet_id: int) -> FieldFilter:
        return cls._equals("source_id", subnet_id)

    @classmethod
    def with_destination_id(cls, subnet_id: int) -> FieldFilter:
        return cls._equals("destination_id", subnet_id)

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> WithVlanId:
        return WithVlanId(vlan_id)

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> WithFabricId:
        return WithFabricId(fabric_id)
