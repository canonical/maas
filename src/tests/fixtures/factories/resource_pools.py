# Factories for the ResourcePool
from datetime import datetime
from typing import Any

from maasservicelayer.models.resource_pools import ResourcePool
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_resource_pool(
    fixture: Fixture, **extra_details: Any
) -> ResourcePool:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    resource_pools = {
        "name": "my_resource_pool",
        "description": "my_description",
        "created": created_at,
        "updated": updated_at,
    }
    resource_pools.update(extra_details)
    [created_resource_pools] = await fixture.create(
        "maasserver_resourcepool",
        [resource_pools],
    )
    return ResourcePool(**created_resource_pools)


async def create_n_test_resource_pools(
    fixture: Fixture, size: int
) -> list[ResourcePool]:
    now = datetime.utcnow().astimezone()
    resource_pools = {
        "name": "my_resource_pool",
        "description": "my_description",
        "created": now,
        "updated": now,
    }

    all_pools = [
        resource_pools | {"name": str(i), "description": str(i)}
        for i in range(size)
    ]
    created_resource_pools = await fixture.create(
        "maasserver_resourcepool",
        all_pools,
    )
    return [
        ResourcePool(**created_pool) for created_pool in created_resource_pools
    ]
