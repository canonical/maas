# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.switches import Switch


class SwitchFilters(FilterFactory):
    model = Switch

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)
