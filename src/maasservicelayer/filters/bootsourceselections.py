# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Iterable

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatus,
)


class BootSourceSelectionFilters(FilterFactory):
    model = BootSourceSelection

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_boot_source_id(cls, boot_source_id: int) -> FieldFilter:
        return cls._equals("boot_source_id", boot_source_id)

    @classmethod
    def with_boot_source_ids(
        cls, boot_source_ids: Iterable[int]
    ) -> FieldFilter:
        return cls._is_in("boot_source_id", boot_source_ids)

    @classmethod
    def with_os(cls, os: str) -> FieldFilter:
        return cls._equals("os", os)

    @classmethod
    def with_release(cls, release: str) -> FieldFilter:
        return cls._equals("release", release)

    @classmethod
    def with_arch(cls, arch: str) -> FieldFilter:
        return cls._equals("arch", arch)

    @classmethod
    def with_legacyselection_id(cls, legacyselection_id: int) -> FieldFilter:
        return cls._equals("legacyselection_id", legacyselection_id)


class BootSourceSelectionStatusFilters(FilterFactory):
    model = BootSourceSelectionStatus

    @classmethod
    def with_selected(cls, selected: bool) -> FieldFilter:
        return cls._equals("selected", selected)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)
