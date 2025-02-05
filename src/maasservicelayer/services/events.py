#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from pydantic import IPvAnyAddress

from maascommon.enums.events import EventTypeEnum
from maascommon.events import EVENT_DETAILS_MAP, EventDetail
from maasservicelayer.builders.events import EventBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.events import (
    EventsRepository,
    EventTypesRepository,
)
from maasservicelayer.models.events import (
    EndpointChoicesEnum,
    Event,
    EventType,
)
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow


class EventsService(BaseService[Event, EventsRepository, EventBuilder]):
    def __init__(
        self,
        context: Context,
        events_repository: EventsRepository,
        eventtypes_repository: EventTypesRepository,
    ):
        super().__init__(context, events_repository)
        self.eventtypes_repository = eventtypes_repository

    async def ensure_event_type(
        self, event_type: EventTypeEnum, detail: EventDetail | None = None
    ) -> EventType:
        detail = detail or EVENT_DETAILS_MAP.get(event_type)
        return await self.eventtypes_repository.ensure(event_type, detail)

    async def record_event(
        self,
        event_type: EventTypeEnum,
        node: Node | None = None,
        hostname: str = "",
        event_action: str = "",
        event_description: str = "",
        user: str | None = None,
        ip_address: IPvAnyAddress | None = None,
        endpoint: EndpointChoicesEnum = EndpointChoicesEnum.API,
        user_agent: str = "",
        created: datetime | None = None,
    ) -> Event:
        et = await self.ensure_event_type(event_type)

        created = created or utcnow()

        return await self.repository.create(
            EventBuilder(
                type=et,
                node_system_id=node.system_id if node else None,
                node_hostname=node.hostname if node else hostname,
                user_id=None,
                owner=user or "",
                endpoint=endpoint,
                user_agent=user_agent,
                description=event_description,
                action=event_action,
                ip_address=ip_address,
                created=created,
            )
        )
