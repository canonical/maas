# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.filters.query import CustomOrderBy, OrderByFactory
from maasservicelayer.models.bootresources import BootResource


@dataclass(frozen=True)
class BootResourceArchitecturePrefix(CustomFilter):
    model: ClassVar = BootResource
    partial_arch: str


@dataclass(frozen=True)
class BootResourceSelectionBootSource(CustomFilter):
    model: ClassVar = BootResource
    boot_source_id: int


@dataclass(frozen=True)
class BootResourceWithFiletype(CustomFilter):
    model: ClassVar = BootResource
    filetype: BootResourceFileType


@dataclass(frozen=True)
class BootResourceNamePriority(CustomOrderBy):
    model: ClassVar = BootResource
    lts_releases: tuple[str, ...]


class BootResourceOrdering(OrderByFactory):
    @staticmethod
    def by_name_with_priority(
        lts_releases: list[str],
    ) -> BootResourceNamePriority:
        return BootResourceNamePriority(tuple(lts_releases))


class BootResourceFilters(FilterFactory):
    model = BootResource

    @classmethod
    def with_name(cls, name: str) -> FieldFilter:
        return cls._equals("name", name)

    @classmethod
    def with_names(cls, names: list[str]) -> FieldFilter:
        return cls._is_in("name", names)

    @classmethod
    def with_architecture(cls, architecture: str) -> FieldFilter:
        return cls._equals("architecture", architecture)

    @classmethod
    def with_architecture_starting_with(
        cls, partial_arch: str
    ) -> BootResourceArchitecturePrefix:
        return BootResourceArchitecturePrefix(partial_arch)

    @classmethod
    def with_alias(cls, alias: str | None) -> FieldFilter:
        return cls._equals("alias", alias)

    @classmethod
    def with_rtype(cls, rtype: BootResourceType) -> FieldFilter:
        return cls._equals("rtype", rtype)

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: Iterable[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_selection_id(cls, selection_id: int) -> FieldFilter:
        return cls._equals("selection_id", selection_id)

    @classmethod
    def with_selection_ids(cls, selection_ids: Iterable[int]) -> FieldFilter:
        return cls._is_in("selection_id", selection_ids)

    @classmethod
    def with_bootloader_type(cls, bootloader_type: str | None) -> FieldFilter:
        return cls._equals("bootloader_type", bootloader_type)

    @classmethod
    def with_selection_boot_source_id(
        cls, boot_source_id: int
    ) -> BootResourceSelectionBootSource:
        return BootResourceSelectionBootSource(boot_source_id)

    @classmethod
    def with_filetype(
        cls, filetype: BootResourceFileType
    ) -> BootResourceWithFiletype:
        return BootResourceWithFiletype(filetype)
