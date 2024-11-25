# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Factories for the Service Status"""

from datetime import datetime, timezone
from typing import Any

from maascommon.enums.service import ServiceName, ServiceStatusEnum
from maasservicelayer.models.service_status import ServiceStatus
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_service_status_entry(
    fixture: Fixture, **extra_details: Any
) -> ServiceStatus:
    created_at = datetime.now(timezone.utc)
    updated_at = datetime.now(timezone.utc)
    service_status = {
        "name": ServiceName.HTTP,
        "status": ServiceStatusEnum.RUNNING,
        "status_info": "",
        "created": created_at,
        "updated": updated_at,
    }
    service_status.update(extra_details)
    if "node_id" not in service_status:
        node = await create_test_region_controller_entry(fixture)
        service_status.update({"node_id": node["id"]})
    [created_service_status] = await fixture.create(
        "maasserver_service", [service_status]
    )
    return ServiceStatus(**created_service_status)
