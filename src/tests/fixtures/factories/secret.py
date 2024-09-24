from datetime import datetime
from typing import Any

from maasservicelayer.models.secrets import Secret
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_secret(fixture: Fixture, **extra_details: Any) -> Secret:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    secret = {
        "created": created_at,
        "updated": updated_at,
        "path": "/path",
        "value": {"data": "mydata"},
    }
    secret.update(extra_details)

    [created_secret] = await fixture.create(
        "maasserver_secret",
        [secret],
    )
    return Secret(**created_secret)
