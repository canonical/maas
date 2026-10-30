# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.machines import Machine


class MachineFilters(FilterFactory):
    model = Machine

    @classmethod
    def with_owner(cls, owner: str | None) -> FieldFilter:
        return cls._equals("owner", owner)

    @classmethod
    def with_resource_pool_ids(cls, rp_ids: set[int] | None) -> FieldFilter:
        return cls._is_in("pool_id", rp_ids if rp_ids is not None else ())
