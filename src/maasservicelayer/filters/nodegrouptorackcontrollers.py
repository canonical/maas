# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.nodegrouptorackcontrollers import (
    NodeGroupToRackController,
)


class NodeGroupToRackControllersFilters(FilterFactory):
    model = NodeGroupToRackController

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> FieldFilter:
        return cls._equals("subnet_id", subnet_id)
