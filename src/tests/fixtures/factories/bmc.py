# Factories for the Zones
from datetime import datetime
from typing import Any

from maasapiserver.v3.models.bmc import Bmc
from maasserver.enum import BMC_TYPE
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bmc_entry(
    fixture: Fixture, **extra_details: Any
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    bmc = {
        "created": created_at,
        "updated": updated_at,
        "power_type": "virsh",
        "bmc_type": BMC_TYPE.BMC,
        "cores": 1,
        "cpu_speed": 100,
        "local_storage": 1024,
        "memory": 1024,
        "name": "mybmc",
        "pool_id": 0,
        "zone_id": 1,
        "cpu_over_commit_ratio": 1,
        "memory_over_commit_ratio": 1,
        "power_parameters": {},
        "version": "1",
    }
    bmc.update(extra_details)
    [created_bmc] = await fixture.create(
        "maasserver_bmc",
        [bmc],
    )
    return created_bmc


async def create_test_bmc(fixture: Fixture, **extra_details: Any) -> Bmc:
    created_bmc = await create_test_bmc_entry(fixture, **extra_details)

    return Bmc(**created_bmc)
