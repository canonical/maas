#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Type

from sqlalchemy import case, insert, join, Select, select, Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.operators import eq, ne, or_

from maascommon.enums.events import EventTypeEnum
from maascommon.events import EventDetail
from maasservicelayer.builders.events import EventTypeBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.mappers.base import BaseDomainDataMapper
from maasservicelayer.db.mappers.event import EventDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import EventTable, EventTypeTable, NodeTable
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.events import Event, EventType
from maasservicelayer.utils.date import utcnow


class EventTypesClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(EventTypeTable.c.name, name))


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


class EventTypesRepository(BaseRepository[EventType]):
    def get_repository_table(self) -> Table:
        return EventTypeTable

    def get_model_factory(self) -> Type[EventType]:
        return EventType

    async def ensure(
        self, event_type: EventTypeEnum, detail: EventDetail
    ) -> EventType:
        async with self.connection.begin_nested():
            try:
                query = QuerySpec(
                    where=EventTypesClauseFactory.with_name(event_type.value)
                )
                if t := await self.get_one(query):
                    return t
                else:
                    return await self.create(
                        EventTypeBuilder(
                            name=event_type.value,
                            description=detail.description,
                            level=detail.level,
                        )
                    )
            except AlreadyExistsException:
                # race, no problem
                pass
        # use outer transaction
        return await self.get_one(query)


class EventsRepository(BaseRepository[Event]):
    def get_repository_table(self) -> Table:
        return EventTable

    def get_model_factory(self) -> Type[Event]:
        return Event

    def get_mapper(self) -> BaseDomainDataMapper:
        return EventDomainDataMapper(self.get_repository_table())

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

    async def _update(self, _query, _builder):
        """Events should not be updated."""
        raise NotImplementedError(
            "The update of events is not a supported operation"
        )

    async def create(self, builder: ResourceBuilder) -> Event:
        resource = self.mapper.build_resource(builder)
        if self.has_timestamped_fields:
            now = utcnow()
            resource["created"] = resource.get("created", now)
            resource["updated"] = resource.get("updated", now)
        stmt = (
            insert(self.get_repository_table())
            .returning(self.get_repository_table().c.id)
            .values(**resource.get_values())
        )
        try:
            result = (await self.execute_stmt(stmt)).one()
            return await self.get_by_id(**result._asdict())
        except IntegrityError:
            self._raise_already_existing_exception()
