from datetime import datetime, timezone
from typing import Any

from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.switches import Switch
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
        "target_image_id": None,
    }
    switch.update(extra_details)

    [created_switch] = await fixture.create(
        "maasserver_switch",
        [switch],
    )
    return created_switch


async def create_test_switch_interface_entry(
    fixture: Fixture, **extra_details: Any
) -> dict[str, Any]:
    """Create a test switch interface database entry."""
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    # Auto-create switch if not provided
    if "switch_id" not in extra_details:
        switch = await create_test_switch_entry(fixture)
        extra_details["switch_id"] = switch["id"]

    interface = {
        "created": created_at,
        "updated": updated_at,
        "mac_address": "00:11:22:33:44:55",
        "name": "mgmt0",
        "type": "physical",
        "params": {},
        "enabled": True,
        "acquired": True,
        "mdns_discovery_state": True,
        "neighbour_discovery_state": True,
        "interface_speed": 0,
        "link_connected": True,
        "link_speed": 0,
        "sriov_max_vf": 0,
    }
    interface.update(extra_details)

    [created_interface] = await fixture.create(
        "maasserver_interface",
        [interface],
    )
    return created_interface


async def create_test_switch(
    fixture: Fixture,
    **extra_details: Any,
) -> Switch:
    """Create a test Switch model instance."""
    switch_data = await create_test_switch_entry(fixture, **extra_details)
    return Switch(**switch_data)


async def create_test_switch_interface(
    fixture: Fixture,
    **extra_details: Any,
) -> Interface:
    """Create a test SwitchInterface model instance."""
    interface_data = await create_test_switch_interface_entry(
        fixture, **extra_details
    )
    return Interface(**interface_data)
