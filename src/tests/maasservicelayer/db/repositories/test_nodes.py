#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maascommon.enums.node import NodeStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.nodes import (
    NodeResourceBuilder,
    NodesRepository,
)
from maasservicelayer.db.tables import BMCTable, NodeTable, ZoneTable
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.zones import Zone
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.user import create_test_user
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestNodesRepository:
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

    async def test_move_bmcs_to_zone(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        [default_zone] = await fixture.get_typed(
            ZoneTable.name, Zone, eq(ZoneTable.c.name, DEFAULT_ZONE_NAME)
        )

        zone_a = await create_test_zone(fixture, name="A")
        zone_b = await create_test_zone(fixture, name="B")

        bmc_a = await create_test_bmc(
            fixture, zone_id=zone_a.id, power_parameters={"a": "a"}
        )
        bmc_b = await create_test_bmc(
            fixture, zone_id=zone_b.id, power_parameters={"b": "b"}
        )
        nodes_repository = NodesRepository(Context(connection=db_connection))
        await nodes_repository.move_bmcs_to_zone(zone_b.id, zone_a.id)

        [updated_bmc_b] = await fixture.get(
            BMCTable.name, eq(BMCTable.c.id, bmc_b.id)
        )
        assert updated_bmc_b["zone_id"] == zone_a.id

        await nodes_repository.move_bmcs_to_zone(zone_a.id, default_zone.id)
        [updated_bmc_a] = await fixture.get(
            BMCTable.name, eq(BMCTable.c.id, bmc_a.id)
        )
        [updated_bmc_b] = await fixture.get(
            BMCTable.name, eq(BMCTable.c.id, bmc_b.id)
        )
        assert updated_bmc_a["zone_id"] == default_zone.id
        assert updated_bmc_b["zone_id"] == default_zone.id

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
        resource = (
            NodeResourceBuilder()
            .with_status(status=NodeStatus.DEPLOYED)
            .build()
        )
        await nodes_repository.update_by_system_id(
            system_id=machine.system_id, resource=resource
        )
        [updated_node] = await fixture.get_typed(
            NodeTable.name, Node, eq(NodeTable.c.id, machine.id)
        )
        assert updated_node.status == NodeStatus.DEPLOYED

        resource = (
            NodeResourceBuilder()
            .with_status(status=NodeStatus.FAILED_DEPLOYMENT)
            .build()
        )
        await nodes_repository.update(id=machine.id, resource=resource)
        [updated_node] = await fixture.get_typed(
            NodeTable.name, Node, eq(NodeTable.c.id, machine.id)
        )
        assert updated_node.status == NodeStatus.FAILED_DEPLOYMENT

    async def test_update_failures(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        nodes_repository = NodesRepository(Context(connection=db_connection))
        resource = (
            NodeResourceBuilder()
            .with_status(status=NodeStatus.DEPLOYED)
            .build()
        )
        with pytest.raises(NotFoundException):
            await nodes_repository.update_by_system_id(
                system_id="mario", resource=resource
            )

        with pytest.raises(NotFoundException):
            await nodes_repository.update(id=-1, resource=resource)
