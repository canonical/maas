from datetime import datetime
from typing import Any

from tests.maasapiserver.fixtures.db import Fixture


async def create_test_fabric_entry(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
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
    return created_fabric
