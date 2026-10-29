#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import case, func, join, or_, Select, select
from sqlalchemy.sql.operators import eq, ne

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.base import (
    ColumnMapping,
    CreateOrUpdateResource,
)
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import EventTable, EventTypeTable, NodeTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.events import EventsOfNodes
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.events import Event


class EventDomainDataMapper(DefaultDomainDataMapper[Event]):
    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        values = builder.populated_fields()
        if "type" in values:
            values["type_id"] = values.pop("type")["id"]
        return self._build_resource(values)

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

    def select_statement(self) -> Select[Any]:
        return (
            select(
                EventTable.c.id.label("id"),
                EventTable.c.created.label("created"),
                EventTable.c.updated.label("updated"),
                EventTable.c.description,
                EventTable.c.action,
                func.json_build_object(
                    "id",
                    EventTypeTable.c.id,
                    "created",
                    EventTypeTable.c.created,
                    "updated",
                    EventTypeTable.c.updated,
                    "name",
                    EventTypeTable.c.name,
                    "description",
                    EventTypeTable.c.description,
                    "level",
                    EventTypeTable.c.level,
                ).label("type"),
                EventTable.c.node_id,
                EventTable.c.node_system_id,
                case(
                    (
                        ne(EventTable.c.node_hostname, None),
                        EventTable.c.node_hostname,
                    ),
                    (
                        ne(NodeTable.c.id, None),
                        NodeTable.c.hostname,
                    ),
                    else_="unknown",
                ).label("node_hostname"),
                EventTable.c.user_id,
                func.coalesce(
                    self.field_mappings()["owner"].column, "unknown"
                ).label("owner"),
                EventTable.c.ip_address,
                EventTable.c.endpoint,
                EventTable.c.user_agent,
            )
            .select_from(EventTable)
            .join(
                EventTypeTable,
                eq(EventTypeTable.c.id, EventTable.c.type_id),
                isouter=True,
            )
            .join(
                NodeTable,
                eq(NodeTable.c.id, EventTable.c.node_id),
                isouter=True,
            )
        )
