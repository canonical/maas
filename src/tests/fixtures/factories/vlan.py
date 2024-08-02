from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from maasservicelayer.db.tables import VlanTable
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_vlan_entry(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    vlan = {
        "created": created_at,
        "updated": updated_at,
        "mtu": 0,
        "dhcp_on": False,
        "description": "",
    }
    vlan.update(extra_details)

    if not vlan.get("fabric_id"):
        fabric = await create_test_fabric_entry(fixture)
        vlan["fabric_id"] = fabric.id

    if not vlan.get("vid"):
        stmt = (
            select(
                postgresql.array_agg(VlanTable.c.vid).label("vids"),
            )
            .select_from(VlanTable)
            .filter(VlanTable.c.fabric_id == vlan["fabric_id"])
        )
        result = (await fixture.conn.execute(stmt)).one()
        for i in range(1, 4095):
            if not result.vids or i not in result.vids:
                vlan["vid"] = i
                break

    [created_vlan] = await fixture.create(
        "maasserver_vlan",
        [vlan],
    )
    return created_vlan
