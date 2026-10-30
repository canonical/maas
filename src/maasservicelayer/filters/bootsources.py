# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.bootsources import BootSource


class BootSourcesFilters(FilterFactory):
    model = BootSource

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_url(cls, url: str) -> FieldFilter:
        return cls._equals("url", url)

    @classmethod
    def with_ids(cls, ids: set[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_priority(cls, priority: int) -> FieldFilter:
        return cls._equals("priority", priority)

    @classmethod
    def with_enabled(cls, enabled: bool) -> FieldFilter:
        return cls._equals("enabled", enabled)
