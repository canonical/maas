from datetime import datetime
from typing import Any

from maasservicelayer.models.interfaces import Interface, Link
from maastesting.factory import factory
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
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


async def create_test_interface(
    fixture: Fixture,
    node: dict[str | Any] | None = None,
    ip_count: int = 4,
    **extra_details: Any,
) -> Interface:
    vlan = await create_test_vlan_entry(fixture)
    subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
    ips = []
    for _ in range(ip_count):
        ips.extend(
            await create_test_staticipaddress_entry(
                fixture=fixture, subnet=subnet, **extra_details
            )
        )

    return await create_test_interface_entry(
        fixture=fixture, node=node, ips=ips, vlan=vlan, **extra_details
    )


async def create_test_interface_dict(
    fixture: Fixture,
    node: dict[str, Any] | None = None,
    ips: list[dict[str, Any]] | None = None,
    vlan: dict[str, Any] | None = None,
    boot_iface: bool | None = None,
    **extra_details: Any,
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
        "link_connected": bool(ips) and len(ips) > 0,
    }
    interface.update(extra_details)

    if node:
        if config_id := node.get("current_config_id"):
            interface["node_config_id"] = config_id
        else:
            config = await create_test_node_config_entry(fixture, node=node)
            interface["node_config_id"] = config["id"]

    if vlan:
        interface["vlan_id"] = vlan["id"]

    [created_interface] = await fixture.create(
        "maasserver_interface",
        [interface],
    )

    # TODO
    # created_interface["effective_mtu"] = int(vlan["mtu"]) if vlan else 0

    if ips:
        for ip in ips:
            await create_test_interface_ip_addresses_entry(
                fixture, created_interface["id"], ip["id"]
            )

    if ips:
        created_interface["links"] = sorted(
            [ip for ip in ips], key=lambda ip: ip["id"], reverse=True
        )

    return created_interface


async def create_test_interface_entry(
    fixture: Fixture,
    node: dict[str, Any] | None = None,
    ips: list[dict[str, Any]] | None = None,
    vlan: dict[str, Any] | None = None,
    **extra_details: Any,
) -> Interface:
    created_interface = await create_test_interface_dict(
        fixture, node, ips, vlan, **extra_details
    )

    created_interface["links"] = sorted(
        [
            Link(
                **{
                    "id": ip["id"],
                    "ip_type": ip["alloc_type"],
                    "ip_address": ip["ip"],
                    "ip_subnet": ip["subnet_id"],
                }
            )
            for ip in created_interface.get("links", [])
        ],
        key=lambda link: link.id,
        reverse=True,
    )

    return Interface(**created_interface)
