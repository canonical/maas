#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.nodeuserdata import NodeUserData


class NodeUserDataFilters(FilterFactory):
    model = NodeUserData

    @classmethod
    def with_node_id(cls, node_id: int) -> FieldFilter:
        return cls._equals("node_id", node_id)

    @classmethod
    def with_for_ephemeral_environment(
        cls, for_ephemeral: bool
    ) -> FieldFilter:
        return cls._equals("for_ephemeral_environment", for_ephemeral)
