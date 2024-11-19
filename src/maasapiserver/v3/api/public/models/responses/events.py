#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maasservicelayer.models.events import Event, EventType, LoggingLevelEnum


class EventTypeLevelEnum(str, Enum):
    AUDIT = "AUDIT"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __str__(self):
        return str(self.value)


LogginLevelEnumResponseMapper = {
    LoggingLevelEnum.AUDIT: EventTypeLevelEnum.AUDIT,
    LoggingLevelEnum.DEBUG: EventTypeLevelEnum.DEBUG,
    LoggingLevelEnum.INFO: EventTypeLevelEnum.INFO,
    LoggingLevelEnum.WARNING: EventTypeLevelEnum.WARNING,
    LoggingLevelEnum.ERROR: EventTypeLevelEnum.ERROR,
    LoggingLevelEnum.CRITICAL: EventTypeLevelEnum.CRITICAL,
}


class EventTypeResponse(BaseModel):
    name: str
    description: str
    level: EventTypeLevelEnum

    @classmethod
    def from_model(cls, event_type: EventType) -> "EventTypeResponse":
        return cls(
            name=event_type.name,
            description=event_type.description,
            level=LogginLevelEnumResponseMapper[event_type.level],
        )


class EventResponse(HalResponse[BaseHal]):
    kind = "Event"
    id: int
    created: datetime
    updated: datetime
    type: EventTypeResponse
    node_system_id: Optional[str]
    node_hostname: str
    user_id: Optional[int]
    owner: str
    ip_address: Optional[IPvAnyAddress]
    user_agent: str
    description: str
    action: str

    @classmethod
    def from_model(
        cls, event: Event, self_base_hyperlink: str
    ) -> "EventResponse":
        return cls(
            id=event.id,
            created=event.created,
            updated=event.updated,
            type=EventTypeResponse.from_model(event.type),
            node_system_id=event.node_system_id,
            node_hostname=event.node_hostname,
            user_id=event.user_id,
            owner=event.owner,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            description=event.description,
            action=event.action,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{event.id}"
                )
            ),
        )


class EventsListResponse(TokenPaginatedResponse[EventResponse]):
    kind = "EventsList"
