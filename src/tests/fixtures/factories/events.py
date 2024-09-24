from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.events import (
    EndpointChoicesEnum,
    Event,
    EventType,
    LoggingLevelEnum,
)
from maasservicelayer.models.machines import Machine
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_event_entry(
    fixture: Fixture,
    event_type: EventType | None = None,
    machine: Machine = None,
    **extra_details: Any
) -> Event:
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)
    event = {
        "created": created_at,
        "updated": updated_at,
        "node_hostname": "",
        "username": "test",
        "user_agent": "",
        "description": "",
        "endpoint": EndpointChoicesEnum.API.value,
        "action": "test",
    }
    event.update(extra_details)

    if machine:
        event["node_id"] = machine.id

    if not event_type:
        event_type = {
            "created": created_at,
            "updated": updated_at,
            "name": "TYPE_TEST",
            "description": "A test type",
            "level": LoggingLevelEnum.AUDIT.value,
        }
        [created_event_type] = await fixture.create(
            "maasserver_eventtype",
            [event_type],
        )
        event_type = EventType(**created_event_type)
    event["type_id"] = event_type.id
    [created_event] = await fixture.create(
        "maasserver_event",
        [event],
    )

    # Reflect the same logic that we have when we extract the record from the DB.
    if not created_event["node_hostname"]:
        if machine:
            created_event["node_hostname"] = machine.hostname
        else:
            created_event["node_hostname"] = "unknown"

    if created_event["username"]:
        created_event["owner"] = created_event["username"]
    else:
        created_event["username"] = "unknown"
    return Event(type=event_type, **created_event)


async def create_test_event_type_entry(
    fixture: Fixture, **extra_details: Any
) -> EventType:
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)
    event_type = {
        "created": created_at,
        "updated": updated_at,
        "name": "TYPE_TEST",
        "description": "A test type",
        "level": LoggingLevelEnum.AUDIT.value,
    }
    event_type.update(extra_details)
    [created_event_type] = await fixture.create(
        "maasserver_eventtype",
        [event_type],
    )
    return EventType(**created_event_type)
