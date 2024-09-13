#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.events import EventsRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.events import Event
from maasservicelayer.services._base import Service


class EventsService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        events_repository: EventsRepository | None = None,
    ):
        super().__init__(connection)
        self.events_repository = (
            events_repository
            if events_repository
            else EventsRepository(connection)
        )

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Event]:
        return await self.events_repository.list(
            token=token, size=size, query=query
        )
