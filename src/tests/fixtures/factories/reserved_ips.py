from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from netaddr import IPAddress, IPNetwork
from sqlalchemy import select

from maasservicelayer.db.tables import ReservedIPTable
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_reserved_ip_entry(
    fixture: Fixture,
    subnet: dict[str, Any] | None = None,
    **extra_details: Any
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    reserved_ip = {
        "created": created_at,
        "updated": updated_at,
        "mac": "01:02:03:04:05:06",
    }

    if subnet:
        reserved_ip["subnet_id"] = subnet["id"]
        reserved_ip["vlan_id"] = subnet["vlan_id"]
        network = IPNetwork(str(subnet["cidr"]))
        ip = IPAddress(network.first)
        while ip != IPAddress(network.last):
            if ip.version == 4:
                comp = IPv4Address(str(ip))
            else:
                comp = IPv6Address(str(ip))
            stmt = (
                select(
                    ReservedIPTable.c.id,
                )
                .select_from(
                    ReservedIPTable,
                )
                .filter(
                    ReservedIPTable.c.ip == comp,
                )
            )
            result = (await fixture.conn.execute(stmt)).one_or_none()
            if not result:
                break
            ip = ip + 1
        reserved_ip["ip"] = str(ip)

    reserved_ip.update(extra_details)

    [created_reserved_ip] = await fixture.create(
        "maasserver_reservedip",
        [reserved_ip],
    )

    return created_reserved_ip
