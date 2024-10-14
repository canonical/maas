from datetime import datetime, timezone
from typing import Any

from maastesting.factory import factory
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_blockdevice_entry(
    fixture: Fixture, node: dict[str, Any], **extra_details: Any
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    blockdevice = {
        "created": created_at,
        "updated": updated_at,
        "name": factory.make_name(),
        "id_path": f"/dev/disk/by-id/{factory.make_name()}",
        "size": 1024 * 1024 * 1024,
        "block_size": 512,
        "tags": [],
        "node_config_id": node["current_config_id"],
    }

    blockdevice.update(extra_details)

    [created_blockdevice] = await fixture.create(
        "maasserver_blockdevice",
        [blockdevice],
    )

    return created_blockdevice
