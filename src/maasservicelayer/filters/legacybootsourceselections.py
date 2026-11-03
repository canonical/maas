# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Iterable

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)


class LegacyBootSourceSelectionFilters(FilterFactory):
    model = LegacyBootSourceSelection

    @classmethod
    def with_ids(cls, ids: Iterable[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_boot_source_id(cls, boot_source_id: int) -> FieldFilter:
        return cls._equals("boot_source_id", boot_source_id)

    @classmethod
    def with_os(cls, os: str) -> FieldFilter:
        return cls._equals("os", os)

    @classmethod
    def with_release(cls, release: str) -> FieldFilter:
        return cls._equals("release", release)
