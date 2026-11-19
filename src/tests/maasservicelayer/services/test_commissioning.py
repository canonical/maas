#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.services import ServiceCollectionV3
from tests.fixtures.factories.interface import create_test_interface_dict
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestIntegrationClearNetworkingConfiguration:
    async def _create_machine_with_config(self, fixture: Fixture) -> dict:
        machine = await create_test_machine_entry(fixture)
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]
        return machine

    async def _link_ids(
        self, services: ServiceCollectionV3, interface_ids: list[int]
    ) -> set[int]:
        return {
            ip.id
            for ip in await services.staticipaddress.get_for_interfaces(
                interface_ids
            )
        }

    @pytest.mark.allow_transactions
    async def test_removes_links_except_discovered(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
        db_connection: AsyncConnection,
    ) -> None:
        machine = await self._create_machine_with_config(fixture)
        subnet = await create_test_subnet_entry(fixture)
        [auto_ip] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
        )
        [static_ip] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet, alloc_type=IpAddressType.STICKY
        )
        [link_up_ip] = await create_test_staticipaddress_entry(
            fixture, alloc_type=IpAddressType.STICKY
        )
        [discovered_ip] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet, alloc_type=IpAddressType.DISCOVERED
        )
        bond = await create_test_interface_dict(
            fixture, node=machine, ips=[auto_ip, static_ip], type="bond"
        )
        physical = await create_test_interface_dict(
            fixture, node=machine, ips=[link_up_ip, discovered_ip, auto_ip]
        )
        node = await services.nodes.update_by_id(
            machine["id"],
            NodeBuilder(
                gateway_link_ipv4_id=auto_ip["id"],
                gateway_link_ipv6_id=static_ip["id"],
            ),
        )
        # Commit the setup so the commit below checks only the clear.
        await db_connection.commit()

        await services.commissioning.clear_networking_configuration(node)
        # Deferred foreign keys are only checked at commit, so this catches
        # rows left referencing a deleted address.
        await db_connection.commit()

        # DISCOVERED links aren't removed.
        assert await self._link_ids(
            services, [bond["id"], physical["id"]]
        ) == {discovered_ip["id"]}
        # Every other link type is deleted.
        for deleted_ip in (auto_ip, static_ip, link_up_ip):
            assert (
                await services.staticipaddress.get_by_id(deleted_ip["id"])
                is None
            )

        # The gateways should have been cleared.
        node = await services.nodes.get_by_id(machine["id"])
        assert node is not None
        assert node.gateway_link_ipv4_id is None
        assert node.gateway_link_ipv6_id is None

    async def test_leaves_other_nodes_untouched(
        self, fixture: Fixture, services: ServiceCollectionV3
    ) -> None:
        machine = await self._create_machine_with_config(fixture)
        other_machine = await self._create_machine_with_config(fixture)
        subnet = await create_test_subnet_entry(fixture)
        [other_ip] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet
        )
        other_interface = await create_test_interface_dict(
            fixture, node=other_machine, ips=[other_ip]
        )
        node = await services.nodes.get_by_id(machine["id"])
        assert node is not None

        await services.commissioning.clear_networking_configuration(node)

        assert await self._link_ids(services, [other_interface["id"]]) == {
            other_ip["id"]
        }
