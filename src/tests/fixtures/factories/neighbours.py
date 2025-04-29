# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any

from maasserver.testing.factory import factory
from maasservicelayer.models.neighbours import Neighbour
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_neighbour_entry(
    fixture: Fixture,
    interface_id: int,
    **extra_details: Any,
) -> Neighbour:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    neighbour = {
        "created": created_at,
        "updated": updated_at,
        "ip": factory.make_ipv4_address(),
        "time": 1,
        "vid": None,
        "count": 1,
        "mac_address": factory.make_mac_address(),
        "interface_id": interface_id,
    }

    neighbour.update(extra_details)

    [created_neighbour] = await fixture.create(
        "maasserver_neighbour",
        [neighbour],
    )

    return Neighbour(**created_neighbour)
