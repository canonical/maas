from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from maasservicelayer.db.tables import NodeConfigTable, NumaNodeTable
from maasservicelayer.utils.date import utcnow
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

    # Boot disks are always physical block devices in MAAS, and the power
    # drivers (and the get-boot-order activity) rely on the physical block
    # device fields "model"/"serial". Create the matching physical block
    # device row so fixtures mirror production and the activity's INNER JOIN
    # against maasserver_physicalblockdevice matches.
    numa_node_id = await _get_or_create_numa_node_id(
        fixture, node["current_config_id"]
    )
    physical_blockdevice = {
        "blockdevice_ptr_id": created_blockdevice["id"],
        "model": factory.make_name("model"),
        "serial": factory.make_name("serial"),
        "firmware_version": None,
        "numa_node_id": numa_node_id,
    }
    [created_physical_blockdevice] = await fixture.create(
        "maasserver_physicalblockdevice",
        [physical_blockdevice],
    )

    return {**created_blockdevice, **created_physical_blockdevice}


async def _get_or_create_numa_node_id(
    fixture: Fixture, node_config_id: int
) -> int:
    """Return a NUMA node id for the config's node, creating one if needed.

    A node has a unique (node_id, index) constraint, so multiple block devices
    on the same node must share a single NUMA node.
    """
    conn = fixture.conn
    [node_id] = (
        await conn.execute(
            select(NodeConfigTable.c.node_id).where(
                NodeConfigTable.c.id == node_config_id
            )
        )
    ).one()

    existing = (
        await conn.execute(
            select(NumaNodeTable.c.id)
            .where(NumaNodeTable.c.node_id == node_id)
            .limit(1)
        )
    ).one_or_none()
    if existing is not None:
        return existing[0]

    now = utcnow()
    [numa_node] = await fixture.create(
        "maasserver_numanode",
        [
            {
                "created": now,
                "updated": now,
                "index": 0,
                "memory": 16384,
                "cores": [0, 1, 2, 3],
                "node_id": node_id,
            }
        ],
    )
    return numa_node["id"]
