# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.db.tables import BootSourceTable
from maasservicelayer.models.bootsources import BootSource
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootsource_entry(
    fixture: Fixture, url, priority, **extra_details
) -> BootSource:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    bootsource = {
        "created": created_at,
        "updated": updated_at,
        "url": url,
        "keyring_filename": "/path/to/keyring.gpg",
        "keyring_data": b"data",
        "priority": priority,
        "skip_keyring_verification": False,
    }
    bootsource.update(extra_details)

    [created_bootsource] = await fixture.create(
        BootSourceTable.name, bootsource
    )

    return BootSource(**created_bootsource)
