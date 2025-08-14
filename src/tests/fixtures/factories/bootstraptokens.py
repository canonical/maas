# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.db.tables import BootstrapTokenTable
from maasservicelayer.models.bootstraptokens import BootstrapToken
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootstraptoken_entry(
    fixture: Fixture,
    secret: str,
    rack_id: int,
    **extra_details,
) -> BootstrapToken:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    expires_at = (
        datetime.now(timezone.utc)
        .astimezone()
        .replace(year=datetime.now(timezone.utc).year + 1)
    )

    bootstraptoken = {
        "created": created_at,
        "updated": updated_at,
        "expires_at": expires_at,
        "secret": secret,
        "rack_id": rack_id,
    }
    bootstraptoken.update(extra_details)

    [created_bootstraptoken] = await fixture.create(
        BootstrapTokenTable.name, bootstraptoken
    )

    return BootstrapToken(**created_bootstraptoken)
