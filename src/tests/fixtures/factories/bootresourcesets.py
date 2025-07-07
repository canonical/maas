# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.tables import BootResourceSetTable
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootresourceset_entry(
    fixture: Fixture, version: str, label: str, resource_id: int
) -> BootResourceSet:
    now = utcnow()
    bootresourceset = {
        "created": now,
        "updated": now,
        "version": version,
        "label": label,
        "resource_id": resource_id,
    }

    [created] = await fixture.create(
        BootResourceSetTable.name, bootresourceset
    )
    return BootResourceSet(**created)
