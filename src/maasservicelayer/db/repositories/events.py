#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from sqlalchemy import case, desc, select, Select
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.operators import eq, le, ne, or_

from maasservicelayer.db.filters import FilterQuery, FilterQueryBuilder
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import EventTable, EventTypeTable, NodeTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.events import Event


class EventsFilterQueryBuilder(FilterQueryBuilder):
    def with_system_ids(
        self, system_ids: Optional[list[str]]
    ) -> FilterQueryBuilder:
        if system_ids is not None:
            self.query.add_clause(
                or_(
                    EventTable.c.node_system_id.in_(system_ids),
                    NodeTable.c.system_id.in_(system_ids),
                )
            )
        return self


class EventsRepository(BaseRepository[Event]):
    async def create(self, resource: CreateOrUpdateResource) -> Event:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> Event | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Event]:
        stmt = (
            self._select_all_statement()
            .order_by(desc(EventTable.c.id))
            .limit(size + 1)
        )
        if query:
            stmt = stmt.where(*query.get_clauses())

        if token is not None:
            stmt = stmt.where(le(EventTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id

        return ListResult[Event](
            items=[Event(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(self, id: int, resource: CreateOrUpdateResource) -> Event:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    def _select_all_statement(self) -> Select[Any]:
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
