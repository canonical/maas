# Factories for the Zones
from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.zones import Zone
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_zone(fixture: Fixture, **extra_details: Any) -> Zone:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    zone = {
        "name": "my_zone",
        "description": "my_description",
        "created": created_at,
        "updated": updated_at,
    }
    zone.update(extra_details)
    [created_zone] = await fixture.create(
        "maasserver_zone",
        [zone],
    )
    return Zone(**created_zone)
