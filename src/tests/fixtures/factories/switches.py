from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.switches import Switch
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_switch_entry(
    fixture: Fixture, **extra_details: Any
) -> dict[str, Any]:
    """Create a test switch database entry."""
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    switch = {
        "created": created_at,
        "updated": updated_at,
        "name": "test-switch",
        "mac_address": "00:11:22:33:44:55",
        "description": "",
    }
    switch.update(extra_details)

    # Auto-create vlan if not provided
    if "vlan_id" not in switch and switch.get("vlan_id") is not False:
        vlan = await create_test_vlan_entry(fixture)
        switch["vlan_id"] = vlan["id"]

    # Auto-create subnet if not provided
    if "subnet_id" not in switch and switch.get("subnet_id") is not False:
        subnet = await create_test_subnet_entry(fixture)
        switch["subnet_id"] = subnet["id"]

    [created_switch] = await fixture.create(
        "maasserver_switch",
        [switch],
    )
    return created_switch


async def create_test_switch(
    fixture: Fixture,
    **extra_details: Any,
) -> Switch:
    """Create a test Switch model instance."""
    switch_data = await create_test_switch_entry(fixture, **extra_details)
    return Switch(**switch_data)
