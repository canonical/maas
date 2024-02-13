from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import array

from maasserver.enum import RDNS_MODE
from maastesting.factory import factory
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_subnet_entry(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    subnet = {
        "created": created_at,
        "updated": updated_at,
        "cidr": str(factory.make_ip4_or_6_network()),
        "rdns_mode": RDNS_MODE.DEFAULT,
        "allow_proxy": True,
        "description": "",
        "active_discovery": False,
        "managed": True,
        "allow_dns": True,
        "disabled_boot_architectures": array([]),
    }
    subnet.update(extra_details)

    if not subnet.get("name"):
        subnet["name"] = subnet["cidr"]

    if not subnet.get("vlan_id"):
        vlan = await create_test_vlan_entry(fixture)
        subnet["vlan_id"] = vlan["id"]

    [created_subnet] = await fixture.create(
        "maasserver_subnet",
        [subnet],
    )
    return created_subnet
