from datetime import datetime
from typing import Any

from sqlalchemy import update

from maasapiserver.common.db.tables import NodeTable
from maastesting.factory import factory
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_node_config_entry(
    fixture: Fixture,
    node: dict[str, Any] | None = None,
    **extra_details: dict[str, Any],
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    config = {
        "created": created_at,
        "updated": updated_at,
        "name": factory.make_name(),
    }
    config.update(extra_details)

    if node:
        config["node_id"] = node["id"]

    [created_config] = await fixture.create(
        "maasserver_nodeconfig",
        [config],
    )

    if node:
        stmt = (
            update(NodeTable)
            .where(
                NodeTable.c.id == node["id"],
            )
            .values(
                current_config_id=created_config["id"],
            )
        )
        await fixture.conn.execute(stmt)

    return created_config
