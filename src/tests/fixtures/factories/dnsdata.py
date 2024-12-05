from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.dnsdata import DNSData
from maasservicelayer.models.dnsresources import DNSResource
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_dnsdata_entry(
    fixture: Fixture, dnsresource: DNSResource, **extra_details: dict[str, Any]
) -> DNSData:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    dnsdata = {
        "rrtype": "TXT",
        "rrdata": "",
        "dnsresource_id": dnsresource.id,
        "created": created_at,
        "updated": updated_at,
    }
    dnsdata.update(extra_details)

    [created_dnsdata] = await fixture.create(
        "maasserver_dnsdata",
        [dnsdata],
    )

    return DNSData(**created_dnsdata)
