#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Type

from sqlalchemy import case, join, Select, select, Table
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.operators import eq, ne, or_

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import EventTable, EventTypeTable, NodeTable
from maasservicelayer.models.events import Event


class EventsClauseFactory(ClauseFactory):
    @classmethod
    def with_system_ids(cls, system_ids: list[str]) -> Clause:
        return Clause(
            condition=or_(
                EventTable.c.node_system_id.in_(system_ids),
                NodeTable.c.system_id.in_(system_ids),
            ),
            joins=[
                join(
                    EventTable,
                    NodeTable,
                    eq(NodeTable.c.id, EventTable.c.node_id),
                )
            ],
        )


class EventsRepository(BaseRepository[Event]):
    def get_repository_table(self) -> Table:
        return EventTable

    def get_model_factory(self) -> Type[Event]:
        return Event

    def select_all_statement(self) -> Select[Any]:
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
                func.coalesce(EventTable.c.username, "unknown").label("owner"),
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
