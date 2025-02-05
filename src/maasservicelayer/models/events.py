#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum
import logging
from typing import Optional

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


class EndpointChoicesEnum(IntEnum):
    API = 0
    UI = 1
    CLI = 2


class LoggingLevelEnum(IntEnum):
    AUDIT = 0
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@generate_builder()
class EventType(MaasTimestampedBaseModel):
    name: str
    description: str
    level: LoggingLevelEnum


@generate_builder()
class Event(MaasTimestampedBaseModel):
    type: EventType
    node_id: Optional[int]
    node_system_id: Optional[str]
    node_hostname: str
    user_id: Optional[int]
    owner: str
    ip_address: Optional[IPvAnyAddress]
    endpoint: EndpointChoicesEnum
    user_agent: str
    description: str
    action: str
