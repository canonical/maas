from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.dnspublications import DNSPublication
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_dnspublication_entry(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> DNSPublication:
    created_at = datetime.now(timezone.utc).astimezone()
    dnspublication = {
        "created": created_at,
        "source": "",
        "update": "",
        "serial": 1,
    }
    dnspublication.update(extra_details)

    [created_dnspublication] = await fixture.create(
        "maasserver_dnspublication",
        [dnspublication],
    )

    return DNSPublication(**created_dnspublication)
