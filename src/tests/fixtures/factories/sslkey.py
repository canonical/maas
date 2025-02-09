# Factories for SSL Keys
from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.sslkeys import SSLKey
from tests.fixtures import get_test_data_file
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_sslkey(fixture: Fixture, **extra_details: Any) -> SSLKey:
    # Build a new test SSL key
    key = get_test_data_file("test_x509_0.pem")

    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    sslkey = {
        "key": key,
        "created": created_at,
        "updated": updated_at,
        "user_id": 1,
    }
    sslkey.update(extra_details)
    [created_sslkey] = await fixture.create(
        "maasserver_sslkey",
        [sslkey],
    )
    return SSLKey(**created_sslkey)
