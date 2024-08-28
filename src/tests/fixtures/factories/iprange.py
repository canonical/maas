from datetime import datetime
from typing import Any

from netaddr import IPAddress, IPNetwork

from tests.maasapiserver.fixtures.db import Fixture


async def create_test_ip_range_entry(
    fixture: Fixture,
    subnet: dict[str, Any],
    offset: int = 0,
    size: int = 5,
    **extra_details: dict[str, Any]
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    ip_range = {
        "created": created_at,
        "updated": updated_at,
        "subnet_id": subnet["id"],
        "type": "reserved",
    }

    network = IPNetwork(str(subnet["cidr"]))
    ip_range["start_ip"] = str(IPAddress(network.first) + offset)
    ip_range["end_ip"] = str(IPAddress(network.first) + offset + size)

    ip_range.update(extra_details)

    [created_ip_range] = await fixture.create(
        "maasserver_iprange",
        [ip_range],
    )

    return created_ip_range
