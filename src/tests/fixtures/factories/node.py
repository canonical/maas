# Factories for Node type sqlalchemy objects
from datetime import datetime, timezone
import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maasservicelayer.db.tables import NodeTable
from maastesting.factory import factory
from provisioningserver.enum import POWER_STATE
from provisioningserver.utils import znums
from tests.maasapiserver.fixtures.db import Fixture


# async implementation of generate_node_system_id from the django model
async def generate_node_system_id(db_connection: AsyncConnection):
    for attempt in range(1, 1001):
        system_num = random.randrange(24**5, 24**6)
        system_id = znums.from_int(system_num)
        stmt = (
            select(NodeTable.c.system_id)
            .select_from(NodeTable)
            .filter(NodeTable.c.system_id == system_id)
        )
        result = (await db_connection.execute(stmt)).one_or_none()
        if not result:
            return system_id
    raise AssertionError(
        "The unthinkable has come to pass: after %d iterations "
        "we could find no unused node identifiers." % attempt
    )


async def _create_test_node_entry(
    fixture: Fixture,
    node_type: NodeTypeEnum,
    **extra_details: Any,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    system_id = await generate_node_system_id(fixture.conn)
    node = {
        "created": created_at,
        "updated": updated_at,
        "system_id": system_id,
        "hostname": factory.make_name(),
        "status": NodeStatus.READY,
        "osystem": "",
        "distro_series": "",
        "cpu_count": 1,
        "memory": 4096,
        "power_state": POWER_STATE.OFF,
        "error": "",
        "netboot": False,
        "enable_ssh": False,
        "skip_networking": False,
        "skip_storage": False,
        "zone_id": 1,
        "url": "",
        "error_description": "",
        "previous_status": NodeStatus.NEW,
        "default_user": "",
        "cpu_speed": 0,
        "install_rackd": False,
        "locked": False,
        "instance_power_parameters": {},
        "install_kvm": False,
        "ephemeral_deploy": False,
        "description": "",
        "dynamic": False,
        "register_vmhost": False,
        "last_applied_storage_layout": "flat",
        "enable_hw_sync": False,
        "node_type": node_type,
        "architecture": "",
        "hwe_kernel": "",
        "enable_kernel_crash_dump": False,
    }
    node.update(extra_details)
    [created_node] = await fixture.create(
        "maasserver_node",
        [node],
    )
    return created_node


async def create_test_machine_entry(
    fixture: Fixture,
    **extra_details: Any,
) -> dict[str, Any]:
    return await _create_test_node_entry(
        fixture, NodeTypeEnum.MACHINE, **extra_details
    )


async def create_test_device_entry(
    fixture: Fixture,
    **extra_details: Any,
) -> dict[str, Any]:
    return await _create_test_node_entry(
        fixture, NodeTypeEnum.DEVICE, **extra_details
    )


async def create_test_rack_controller_entry(
    fixture: Fixture,
    **extra_details: Any,
) -> dict[str, Any]:
    return await _create_test_node_entry(
        fixture, NodeTypeEnum.RACK_CONTROLLER, **extra_details
    )


async def create_test_region_controller_entry(
    fixture: Fixture,
    **extra_details: Any,
) -> dict[str, Any]:
    return await _create_test_node_entry(
        fixture, NodeTypeEnum.REGION_CONTROLLER, **extra_details
    )


async def create_test_rack_and_region_controller_entry(
    fixture: Fixture,
    **extra_details: Any,
) -> dict[str, Any]:
    return await _create_test_node_entry(
        fixture, NodeTypeEnum.REGION_AND_RACK_CONTROLLER, **extra_details
    )
