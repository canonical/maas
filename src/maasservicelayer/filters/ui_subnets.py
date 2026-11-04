# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar, Literal

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.filters.query import OrderBy, OrderByFactory
from maasservicelayer.models.ui_subnets import UISubnet


@dataclass(frozen=True)
class UISubnetsCIDRsFilter(CustomFilter):
    model: ClassVar = UISubnet
    cidrs: tuple[str, ...]


@dataclass(frozen=True)
class UISubnetsContainsFilter(CustomFilter):
    model: ClassVar = UISubnet
    field: Literal["fabric_name", "vlan_name", "space_name", "cidr"]
    value: str


class UISubnetsFilters(FilterFactory):
    model = UISubnet

    @classmethod
    def with_cidrs(cls, cidrs: list[str]) -> UISubnetsCIDRsFilter:
        return UISubnetsCIDRsFilter(tuple(cidrs))

    @classmethod
    def with_vlan_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("vlan_id", ids)

    @classmethod
    def with_fabric_names(cls, names: list[str]) -> FieldFilter:
        return cls._is_in("fabric_name", names)

    @classmethod
    def with_space_names(cls, names: list[str]) -> FieldFilter:
        return cls._is_in("space_name", names)

    @classmethod
    def with_fabric_name_like(
        cls, partial_name: str
    ) -> UISubnetsContainsFilter:
        return UISubnetsContainsFilter("fabric_name", partial_name)

    @classmethod
    def with_vlan_name_like(cls, partial_name: str) -> UISubnetsContainsFilter:
        return UISubnetsContainsFilter("vlan_name", partial_name)

    @classmethod
    def with_space_name_like(
        cls, partial_name: str
    ) -> UISubnetsContainsFilter:
        return UISubnetsContainsFilter("space_name", partial_name)

    @classmethod
    def with_cidr_like(cls, partial_cidr: str) -> UISubnetsContainsFilter:
        return UISubnetsContainsFilter("cidr", partial_cidr)

    @classmethod
    def with_subnet_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)


class UISubnetsOrdering(OrderByFactory):
    @staticmethod
    def by_cidr() -> OrderBy:
        return OrderBy(UISubnet, "cidr")

    @staticmethod
    def by_fabric_name() -> OrderBy:
        return OrderBy(UISubnet, "fabric_name")

    @staticmethod
    def by_space_name() -> OrderBy:
        return OrderBy(UISubnet, "space_name")
