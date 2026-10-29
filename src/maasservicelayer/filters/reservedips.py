# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.reservedips import ReservedIP


@dataclass(frozen=True)
class WithVlanId(CustomFilter):
    model: ClassVar = ReservedIP
    vlan_id: int


@dataclass(frozen=True)
class WithFabricId(CustomFilter):
    model: ClassVar = ReservedIP
    fabric_id: int


class ReservedIPsFilters(FilterFactory):
    model = ReservedIP

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> FieldFilter:
        return cls._equals("subnet_id", subnet_id)

    @classmethod
    def with_subnet_id_in(cls, subnet_ids: list[int]) -> FieldFilter:
        return cls._is_in("subnet_id", subnet_ids)

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> WithVlanId:
        return WithVlanId(vlan_id)

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> WithFabricId:
        return WithFabricId(fabric_id)
