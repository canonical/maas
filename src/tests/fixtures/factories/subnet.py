from datetime import datetime, timezone
from operator import eq
from typing import Any

from sqlalchemy.dialects.postgresql import array

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.db.tables import UISubnetView
from maasservicelayer.models.spaces import Space
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.models.vlans import Vlan
from maastesting.factory import factory
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_subnet_entry(
    fixture: Fixture, **extra_details: Any
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    subnet = {
        "created": created_at,
        "updated": updated_at,
        "cidr": str(factory.make_ip4_or_6_network()),
        "rdns_mode": RdnsMode.DEFAULT,
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


async def create_test_ui_subnet_entry(
    fixture: Fixture,
    space: Space | None = None,
    vlan: Vlan | None = None,
    **extra_details,
) -> UISubnet:
    if not space:
        space = await create_test_space_entry(fixture)
    if not vlan:
        vlan = Vlan(**await create_test_vlan_entry(fixture, space_id=space.id))
    subnet = await create_test_subnet_entry(
        fixture, vlan_id=vlan.id, **extra_details
    )
    [ui_subnet] = await fixture.get_typed(
        UISubnetView.name, UISubnet, eq(UISubnetView.c.id, subnet["id"])
    )
    return ui_subnet
