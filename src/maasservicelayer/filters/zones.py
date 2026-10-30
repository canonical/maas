# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.zones import Zone


class ZonesFilters(FilterFactory):
    model = Zone

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)
