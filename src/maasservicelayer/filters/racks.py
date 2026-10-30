# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.racks import Rack


class RacksFilters(FilterFactory):
    model = Rack

    @classmethod
    def with_rack_id(cls, rack_id: int) -> FieldFilter:
        return cls._equals("id", rack_id)
