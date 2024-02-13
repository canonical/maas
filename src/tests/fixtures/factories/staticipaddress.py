from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from netaddr import IPAddress, IPNetwork
from sqlalchemy import select

from maasapiserver.common.db.tables import StaticIPAddressTable
from maasserver.enum import IPADDRESS_TYPE
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_staticipaddress_entry(
    fixture: Fixture,
    subnet: dict[str, Any] | None = None,
    **extra_details: dict[str, Any]
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    staticipaddress = {
        "created": created_at,
        "updated": updated_at,
        "alloc_type": IPADDRESS_TYPE.AUTO,
        "lease_time": 600,
    }
    staticipaddress.update(extra_details)

    if subnet:
        staticipaddress["subnet_id"] = subnet["id"]
        network = IPNetwork(str(subnet["cidr"]))
        ip = IPAddress(network.first)
        while ip != IPAddress(network.last):
            if ip.version == 4:
                comp = IPv4Address(str(ip))
            else:
                comp = IPv6Address(str(ip))
            stmt = (
                select(
                    StaticIPAddressTable.c.id,
                )
                .select_from(
                    StaticIPAddressTable,
                )
                .filter(
                    StaticIPAddressTable.c.ip == comp,
                )
            )
            result = (await fixture.conn.execute(stmt)).one_or_none()
            if not result:
                break
            ip = ip + 1
        staticipaddress["ip"] = str(ip)

    [created_staticipaddress] = await fixture.create(
        "maasserver_staticipaddress",
        [staticipaddress],
    )

    return created_staticipaddress
