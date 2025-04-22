# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.staticroutes import StaticRoute
from maasservicelayer.models.subnets import Subnet
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_staticroute_entry(
    fixture: Fixture,
    source_subnet: Subnet,
    destination_subnet: Subnet,
    **extra_details: Any,
) -> StaticRoute:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    gateway_ip = source_subnet.cidr[0]
    staticroute = {
        "created": created_at,
        "updated": updated_at,
        "gateway_ip": gateway_ip,
        "source_id": source_subnet.id,
        "destination_id": destination_subnet.id,
        "metric": 0,
    }

    staticroute.update(extra_details)

    [created_staticroute] = await fixture.create(
        "maasserver_staticroute",
        [staticroute],
    )

    return StaticRoute(**created_staticroute)
