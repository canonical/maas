#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join, or_

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    ColumnMapping,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import EventTable, NodeTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.events import EventsOfNodes
from maasservicelayer.models.base import ResourceBuilder


class EventDomainDataMapper(BaseDomainDataMapper):
    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        for name, value in builder.populated_fields().items():
            match name:
                case "type":
                    name = f"{name}_id"
                    value = value["id"]
                case "owner":
                    name = "username"

            resource.set_value(self.table_columns[name].name, value)
        return resource

    def field_mappings(self) -> dict[str, ColumnMapping]:
        return {"owner": ColumnMapping(EventTable.c.username)}

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case EventsOfNodes(system_ids):
                return Clause(
                    condition=or_(
                        EventTable.c.node_system_id.in_(system_ids),
                        NodeTable.c.system_id.in_(system_ids),
                    ),
                    # Outer join: events of deleted nodes keep their system
                    # id but lose their node_id, and they must still match.
                    joins=[
                        join(
                            EventTable,
                            NodeTable,
                            NodeTable.c.id == EventTable.c.node_id,
                            isouter=True,
                        )
                    ],
                )
        return super().custom_filter_clause(filter)
