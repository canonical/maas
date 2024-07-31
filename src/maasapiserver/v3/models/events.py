#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
from typing import Optional

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.events import (
    EventResponse,
    EventTypeLevelEnum,
    EventTypeResponse,
)
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class EndpointChoicesEnum(Enum):
    API = 0
    UI = 1
    CLI = 2


class LoggingLevelEnum(Enum):
    AUDIT = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


LogginLevelEnumResponseMapper = {
    LoggingLevelEnum.AUDIT: EventTypeLevelEnum.AUDIT,
    LoggingLevelEnum.DEBUG: EventTypeLevelEnum.DEBUG,
    LoggingLevelEnum.INFO: EventTypeLevelEnum.INFO,
    LoggingLevelEnum.WARNING: EventTypeLevelEnum.WARNING,
    LoggingLevelEnum.ERROR: EventTypeLevelEnum.ERROR,
    LoggingLevelEnum.CRITICAL: EventTypeLevelEnum.CRITICAL,
}


class EventType(MaasTimestampedBaseModel):
    name: str
    description: str
    level: LoggingLevelEnum

    def to_response(self) -> EventTypeResponse:
        return EventTypeResponse(
            name=self.name,
            description=self.description,
            level=LogginLevelEnumResponseMapper[self.level],
        )


class Event(MaasTimestampedBaseModel):
    type: EventType
    node_system_id: Optional[str]
    node_hostname: str
    user_id: Optional[int]
    owner: str
    ip_address: Optional[IPvAnyAddress]
    endpoint: EndpointChoicesEnum
    user_agent: str
    description: str
    action: str

    def to_response(self, self_base_hyperlink: str) -> EventResponse:
        return EventResponse(
            id=self.id,
            created=self.created,
            updated=self.updated,
            type=self.type.to_response(),
            node_system_id=self.node_system_id,
            node_hostname=self.node_hostname,
            user_id=self.user_id,
            owner=self.owner,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            description=self.description,
            action=self.action,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
