#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.db.tables import NodeTable, ZoneTable
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.zones import Zone
from tests.fixtures.factories.node import create_test_machine_entry
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
        nodes_repository = NodesRepository(db_connection)
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
