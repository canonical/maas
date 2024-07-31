#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, IPvAnyAddress

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    TokenPaginatedResponse,
)


class EventTypeLevelEnum(str, Enum):
    AUDIT = "AUDIT"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventTypeResponse(BaseModel):
    name: str
    description: str
    level: EventTypeLevelEnum


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


class EventsListResponse(TokenPaginatedResponse[EventResponse]):
    kind = "EventsList"
