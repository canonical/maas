# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.filters.query import OrderBy, OrderByFactory
from maasservicelayer.models.bootresourcesets import BootResourceSet


@dataclass(frozen=True)
class BootResourceSetVersionPrefix(CustomFilter):
    model: ClassVar = BootResourceSet
    version: str


class BootResourceSetFilters(FilterFactory):
    model = BootResourceSet

    @classmethod
    def with_ids(cls, ids: set[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_resource_id(cls, resource_id: int) -> FieldFilter:
        return cls._equals("resource_id", resource_id)

    @classmethod
    def with_resource_ids(cls, resource_ids: list[int]) -> FieldFilter:
        return cls._is_in("resource_id", resource_ids)

    @classmethod
    def with_version(cls, version: str) -> FieldFilter:
        return cls._equals("version", version)

    @classmethod
    def with_version_prefix(cls, version: str) -> BootResourceSetVersionPrefix:
        return BootResourceSetVersionPrefix(version)

    @classmethod
    def with_label(cls, label: str) -> FieldFilter:
        return cls._equals("label", label)


class BootResourceSetsOrdering(OrderByFactory):
    @staticmethod
    def by_id() -> OrderBy:
        return OrderBy(BootResourceSet, "id")
