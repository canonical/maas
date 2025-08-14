# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.db.tables import RackTable
from maasservicelayer.models.racks import Rack
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_rack_entry(
    fixture: Fixture, name: str, **extra_details
) -> Rack:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    rack = {
        "created": created_at,
        "updated": updated_at,
        "name": name,
    }
    rack.update(extra_details)

    [created_rack] = await fixture.create(RackTable.name, rack)

    return Rack(**created_rack)
