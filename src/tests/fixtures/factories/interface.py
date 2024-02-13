from datetime import datetime
from typing import Any

from maastesting.factory import factory
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_interface_ip_addresses_entry(
    fixture: Fixture,
    interface_id: int,
    ip_id: int,
):
    record = {
        "interface_id": interface_id,
        "staticipaddress_id": ip_id,
    }

    [created_record] = await fixture.create(
        "maasserver_interface_ip_addresses",
        [record],
    )
    return created_record


async def create_test_interface_entry(
    fixture: Fixture,
    node: dict[str, Any] | None = None,
    ips: list[dict[str, Any]] | None = None,
    **extra_details: dict[str, Any],
) -> dict[str, Any]:
    created_at = datetime.utcnow().astimezone()
    updated_at = datetime.utcnow().astimezone()
    interface = {
        "created": created_at,
        "updated": updated_at,
        "name": factory.make_name(),
        "type": "physical",
        "mac_address": factory.make_mac_address(),
        "params": {},
        "enabled": True,
        "acquired": False,
        "mdns_discovery_state": False,
        "neighbour_discovery_state": False,
        "interface_speed": 1024,
        "link_speed": 1024,
        "sriov_max_vf": 4,
        "link_connected": len(ips) > 0,
    }
    interface.update(extra_details)

    if node:
        config_id = node.get("current_config_id")
        if config_id:
            interface["node_config_id"] = config_id
        else:
            config = await create_test_node_config_entry(fixture, node=node)
            interface["node_config_id"] = config["id"]

    [created_interface] = await fixture.create(
        "maasserver_interface",
        [interface],
    )

    if ips:
        for ip in ips:
            await create_test_interface_ip_addresses_entry(
                fixture, created_interface["id"], ip["id"]
            )

    return created_interface
