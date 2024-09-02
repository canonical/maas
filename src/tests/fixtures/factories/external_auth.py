#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Any

from maasapiserver.common.utils.date import utcnow
from maasservicelayer.models.external_auth import RootKey
from tests.maasapiserver.fixtures.db import Fixture


async def create_rootkey(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> RootKey:
    created_at = utcnow()
    updated_at = utcnow()

    rootkey = {
        "created": created_at,
        "updated": updated_at,
        "expiration": created_at + timedelta(days=2),
    }
    rootkey.update(extra_details)

    [created_rootkey] = await fixture.create(
        "maasserver_rootkey",
        [rootkey],
    )
    return RootKey(**created_rootkey)
