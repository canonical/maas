# Factories for the Zones
from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.vmcluster import VmCluster
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_vmcluster(
    fixture: Fixture, **extra_details: Any
) -> VmCluster:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    vmcluster = {
        "name": "myvmcluster",
        "project": "myproject",
        "created": created_at,
        "updated": updated_at,
        "zone_id": 1,
        "pool_id": 0,
    }
    vmcluster.update(extra_details)
    [created_vmcluster] = await fixture.create(
        "maasserver_vmcluster",
        [vmcluster],
    )
    return VmCluster(**created_vmcluster)
