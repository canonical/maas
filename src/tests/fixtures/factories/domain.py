from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.domains import Domain
from maastesting.factory import factory
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_domain_entry(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> Domain:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    domain = {
        "created": created_at,
        "updated": updated_at,
        "name": factory.make_name(),
        "authoritative": True,
        "ttl": 30,
    }
    domain.update(extra_details)

    [created_domain] = await fixture.create(
        "maasserver_domain",
        [domain],
    )
    return Domain(**created_domain)
