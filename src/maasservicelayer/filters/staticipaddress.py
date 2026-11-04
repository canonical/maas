# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import ClassVar, List

from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.staticipaddress import StaticIPAddress


@dataclass(frozen=True)
class StaticIPAddressNodeTypeFilter(CustomFilter):
    model: ClassVar = StaticIPAddress
    node_type: NodeTypeEnum


@dataclass(frozen=True)
class StaticIPAddressNodeSystemIDFilter(CustomFilter):
    model: ClassVar = StaticIPAddress
    system_id: str


@dataclass(frozen=True)
class StaticIPAddressLinkedToInterfaceFilter(CustomFilter):
    model: ClassVar = StaticIPAddress


@dataclass(frozen=True)
class StaticIPAddressAllocTypeNotInFilter(CustomFilter):
    model: ClassVar = StaticIPAddress
    alloc_types: tuple[IpAddressType, ...]


@dataclass(frozen=True)
class StaticIPAddressInterfaceEnabledFilter(CustomFilter):
    model: ClassVar = StaticIPAddress
    enabled: bool


@dataclass(frozen=True)
class StaticIPAddressNotNullFilter(CustomFilter):
    model: ClassVar = StaticIPAddress


@dataclass(frozen=True)
class StaticIPAddressInterfaceIDsFilter(CustomFilter):
    model: ClassVar = StaticIPAddress
    interface_ids: tuple[int, ...]


class StaticIPAddressFilters(FilterFactory):
    model = StaticIPAddress

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_node_type(
        cls, type: NodeTypeEnum
    ) -> StaticIPAddressNodeTypeFilter:
        return StaticIPAddressNodeTypeFilter(type)

    @classmethod
    def with_node_system_id(
        cls, system_id: str
    ) -> StaticIPAddressNodeSystemIDFilter:
        return StaticIPAddressNodeSystemIDFilter(system_id)

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> FieldFilter:
        return cls._equals("subnet_id", subnet_id)

    @classmethod
    def with_subnet_id_in(cls, subnet_ids: list[int]) -> FieldFilter:
        return cls._is_in("subnet_id", subnet_ids)

    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address | None) -> FieldFilter:
        return cls._equals("ip", ip)

    @classmethod
    def with_user_id(cls, user_id: int) -> FieldFilter:
        return cls._equals("user_id", user_id)

    @classmethod
    def with_alloc_type(cls, alloc_type: IpAddressType) -> FieldFilter:
        return cls._equals("alloc_type", alloc_type)

    @classmethod
    def with_linked_to_interface(
        cls,
    ) -> StaticIPAddressLinkedToInterfaceFilter:
        return StaticIPAddressLinkedToInterfaceFilter()

    @classmethod
    def with_alloc_type_not_in(
        cls, alloc_types: List[IpAddressType]
    ) -> StaticIPAddressAllocTypeNotInFilter:
        return StaticIPAddressAllocTypeNotInFilter(tuple(alloc_types))

    @classmethod
    def with_alloc_type_in(
        cls, alloc_types: list[IpAddressType]
    ) -> FieldFilter:
        return cls._is_in("alloc_type", alloc_types)

    @classmethod
    def with_temp_expires_on_is_null(cls) -> FieldFilter:
        return cls._equals("temp_expires_on", None)

    @classmethod
    def with_interface_enabled(
        cls, enabled: bool
    ) -> StaticIPAddressInterfaceEnabledFilter:
        return StaticIPAddressInterfaceEnabledFilter(enabled)

    @classmethod
    def with_ip_not_null(cls) -> StaticIPAddressNotNullFilter:
        return StaticIPAddressNotNullFilter()

    @classmethod
    def with_interface_ids(
        cls, interface_ids: List[int]
    ) -> StaticIPAddressInterfaceIDsFilter:
        return StaticIPAddressInterfaceIDsFilter(tuple(interface_ids))
