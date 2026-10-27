# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.db.tables import RackControllerTable
from maasservicelayer.models.rackcontrollers import RackController
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_rack_controller_entry(
    fixture: Fixture,
    uuid: str,
    rack_id: int,
    node_id: int,
    **extra_details,
) -> RackController:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    rack_controller = {
        "created": created_at,
        "updated": updated_at,
        "uuid": uuid,
        "rack_id": rack_id,
        "node_id": node_id,
    }
    rack_controller.update(extra_details)

    [created_rack_controller] = await fixture.create(
        RackControllerTable.name, rack_controller
    )

    return RackController(**created_rack_controller)
