# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maascommon.enums.node import NodeStatus
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.db.tables import NodeTable, ZoneTable
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.filters.nodes import NodeFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.zones import Zone
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.user import create_test_user
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestNodesRepository:
    async def test_get_many_with_current_node_configuration(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        node = await create_test_machine_entry(fixture)
        old_config = await create_test_node_config_entry(fixture, node=node)
        current_config = await create_test_node_config_entry(
            fixture, node=node
        )
        repository = NodesRepository(Context(connection=db_connection))

        assert (
            await repository.get_many(
                QuerySpec(
                    where=NodeFilters.with_node_config_id(old_config["id"])
                )
            )
            == []
        )
        nodes = await repository.get_many(
            QuerySpec(
                where=NodeFilters.with_node_config_id(current_config["id"])
            )
        )
        assert [result.id for result in nodes] == [node["id"]]

    @pytest.mark.parametrize("url", ["", "http://region:5240/MAAS"])
    async def test_get_url(
        self, db_connection: AsyncConnection, fixture: Fixture, url: str
    ) -> None:
        node = await create_test_machine_entry(fixture, url=url)
        repository = NodesRepository(Context(connection=db_connection))
        assert await repository.get_url(node["system_id"]) == url
        assert await repository.get_url("missing") is None

    async def test_move_to_zone(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        [default_zone] = await fixture.get_typed(
            ZoneTable.name, Zone, eq(ZoneTable.c.name, DEFAULT_ZONE_NAME)
        )

        zone_a = await create_test_zone(fixture, name="A")
        zone_b = await create_test_zone(fixture, name="B")

        node_a = Node(
            **(
                await create_test_machine_entry(
                    fixture, system_id="a", zone_id=zone_a.id
                )
            )
        )
        node_b = Node(
            **(
                await create_test_machine_entry(
                    fixture, system_id="b", zone_id=zone_b.id
                )
            )
        )
        nodes_repository = NodesRepository(Context(connection=db_connection))
        await nodes_repository.move_to_zone(zone_b.id, zone_a.id)

        [updated_node_b] = await fixture.get(
            NodeTable.name, eq(NodeTable.c.id, node_b.id)
        )
        assert updated_node_b["zone_id"] == zone_a.id

        await nodes_repository.move_to_zone(zone_a.id, default_zone.id)
        [updated_node_a] = await fixture.get(
            NodeTable.name, eq(NodeTable.c.id, node_a.id)
        )
        [updated_node_b] = await fixture.get(
            NodeTable.name, eq(NodeTable.c.id, node_b.id)
        )
        assert updated_node_a["zone_id"] == default_zone.id
        assert updated_node_b["zone_id"] == default_zone.id

    async def test_get_node_bmc(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = await create_test_machine(fixture, bmc=bmc, user=user)
        nodes_repository = NodesRepository(Context(connection=db_connection))
        node_bmc = await nodes_repository.get_node_bmc(machine.system_id)

        assert node_bmc is not None
        assert node_bmc.id == bmc.id
        assert node_bmc.power_type == bmc.power_type
        assert node_bmc.power_parameters == bmc.power_parameters

    async def test_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = await create_test_machine(
            fixture, bmc=bmc, user=user, status=NodeStatus.NEW
        )

        nodes_repository = NodesRepository(Context(connection=db_connection))
        builder = NodeBuilder(status=NodeStatus.DEPLOYED)
        await nodes_repository.update_one(
            query=QuerySpec(
                where=NodeFilters.with_system_id(machine.system_id)
            ),
            builder=builder,
        )
        [updated_node] = await fixture.get_typed(
            NodeTable.name, Node, eq(NodeTable.c.id, machine.id)
        )
        assert updated_node.status == NodeStatus.DEPLOYED

        builder = NodeBuilder(status=NodeStatus.FAILED_DEPLOYMENT)
        await nodes_repository.update_by_id(id=machine.id, builder=builder)
        [updated_node] = await fixture.get_typed(
            NodeTable.name, Node, eq(NodeTable.c.id, machine.id)
        )
        assert updated_node.status == NodeStatus.FAILED_DEPLOYMENT

    async def test_update_failures(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        nodes_repository = NodesRepository(Context(connection=db_connection))
        builder = NodeBuilder(status=NodeStatus.DEPLOYED)
        with pytest.raises(NotFoundException):
            await nodes_repository.update_one(
                query=QuerySpec(NodeFilters.with_system_id("mario")),
                builder=builder,
            )

        with pytest.raises(NotFoundException):
            await nodes_repository.update_by_id(id=-1, builder=builder)
