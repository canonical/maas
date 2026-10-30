# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.resource_pools import ResourcePool


class ResourcePoolFilters(FilterFactory):
    model = ResourcePool

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)
