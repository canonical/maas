from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert

from maasservicelayer.db.tables import DNSResourceIPAddressTable
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maastesting.factory import factory
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_dnsresource_entry(
    fixture: Fixture,
    domain: Domain,
    ip: dict[str, Any] | None = None,
    **extra_details: dict[str, Any],
) -> DNSResource:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    dnsresource = {
        "created": created_at,
        "updated": updated_at,
        "name": factory.make_name(),
        "domain_id": domain.id,
        "address_ttl": 30,
    }
    dnsresource.update(extra_details)

    [created_dnsresource] = await fixture.create(
        "maasserver_dnsresource",
        [dnsresource],
    )

    if ip:
        stmt = insert(DNSResourceIPAddressTable).values(
            staticipaddress_id=ip["id"],
            dnsresource_id=created_dnsresource["id"],
        )
        await fixture.conn.execute(stmt)

    return DNSResource(**created_dnsresource)
