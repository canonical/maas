# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from pydantic import IPvAnyAddress

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.ipranges import IPRange


@dataclass(frozen=True)
class IPRangeVlanFilter(CustomFilter):
    model: ClassVar = IPRange
    vlan_id: int


@dataclass(frozen=True)
class IPRangeFabricFilter(CustomFilter):
    model: ClassVar = IPRange
    fabric_id: int


class IPRangeFilters(FilterFactory):
    model = IPRange

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> FieldFilter:
        return cls._equals("subnet_id", subnet_id)

    @classmethod
    def with_subnet_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("subnet_id", ids)

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> IPRangeVlanFilter:
        return IPRangeVlanFilter(vlan_id)

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> IPRangeFabricFilter:
        return IPRangeFabricFilter(fabric_id)

    @classmethod
    def with_start_ip(cls, ip: IPvAnyAddress) -> FieldFilter:
        return cls._equals("start_ip", ip)

    @classmethod
    def with_end_ip(cls, ip: IPvAnyAddress) -> FieldFilter:
        return cls._equals("end_ip", ip)

    @classmethod
    def with_type(cls, type: IPRangeType) -> FieldFilter:
        return cls._equals("type", type)

    @classmethod
    def with_user_id(cls, user_id: int) -> FieldFilter:
        return cls._equals("user_id", user_id)
