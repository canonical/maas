#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import insert, Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.events import EventTypeEnum
from maascommon.events import EventDetail
from maasservicelayer.builders.events import EventTypeBuilder
from maasservicelayer.db.mappers.event import EventDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import EventTable, EventTypeTable
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.filters.events import EventTypeFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.events import Event, EventType
from maasservicelayer.utils.date import utcnow


class EventTypesRepository(BaseRepository[EventType]):
    def get_repository_table(self) -> Table:
        return EventTypeTable

    def get_model_factory(self) -> Type[EventType]:
        return EventType

    async def ensure(
        self, event_type: EventTypeEnum, detail: EventDetail
    ) -> EventType:
        query = QuerySpec(where=EventTypeFilters.with_name(event_type.value))
        if t := await self.get_one(query):
            return t
        else:
            try:
                connection = self.context.get_connection()
                if isinstance(connection, AsyncConnection):
                    async with connection.begin_nested():
                        return await self.create(
                            EventTypeBuilder(
                                name=event_type.value,
                                description=detail.description,
                                level=detail.level,
                            )
                        )
                else:
                    with connection.begin_nested():
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
        return await self.get_one(query)  # pyright: ignore [reportReturnType]


class EventsRepository(BaseRepository[Event]):
    def get_repository_table(self) -> Table:
        return EventTable

    def get_model_factory(self) -> Type[Event]:
        return Event

    def get_mapper(self) -> EventDomainDataMapper:
        return EventDomainDataMapper(Event, self.get_repository_table())

    async def _update(self, query, builder):
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
            return await self.get_by_id(result.id)  # pyright: ignore [reportReturnType]
        except IntegrityError:
            self._raise_already_existing_exception()
