from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.fabrics import Fabric
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_fabric_entry(
    fixture: Fixture, **extra_details: Any
) -> Fabric:
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)
    fabric = {
        "created": created_at,
        "updated": updated_at,
        "description": "",
    }
    fabric.update(extra_details)
    [created_fabric] = await fixture.create(
        "maasserver_fabric",
        [fabric],
    )
    return Fabric(**created_fabric)
