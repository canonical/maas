#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.events import EventsRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.events import Event
from maasservicelayer.db.filters import FilterQuery


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
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Event]:
        return await self.events_repository.list(
            token=token, size=size, query=query
        )
