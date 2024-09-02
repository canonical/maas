#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
from typing import Optional

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import MaasTimestampedBaseModel


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


class EventType(MaasTimestampedBaseModel):
    name: str
    description: str
    level: LoggingLevelEnum


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
