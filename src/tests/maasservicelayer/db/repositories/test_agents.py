# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.agents import AgentBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.agents import AgentsRepository
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.filters.agents import AgentsFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.agents import Agent
from tests.fixtures.factories.agents import create_test_agents_entry
from tests.fixtures.factories.node import create_test_rack_controller_entry
from tests.fixtures.factories.racks import create_test_rack_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestAgentsRepository(RepositoryCommonTests[Agent]):
    @pytest.mark.parametrize(
        "filter_factory",
        [
            lambda agent: AgentsFilters.with_id(agent.id),
            lambda agent: AgentsFilters.with_rack_id(agent.rack_id),
            lambda agent: AgentsFilters.with_rack_id_in([agent.rack_id]),
            lambda agent: AgentsFilters.with_uuid(agent.uuid),
        ],
    )
    async def test_get_many_with_domain_filters(
        self,
        repository_instance: AgentsRepository,
        created_instance: Agent,
        filter_factory,
    ) -> None:
        assert await repository_instance.get_many(
            QuerySpec(where=filter_factory(created_instance))
        ) == [created_instance]

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Agent]:
        racks = [
            await create_test_rack_entry(fixture, name=f"rack-{i}")
            for i in range(num_objects)
        ]
        rack_controllers = [
            await create_test_rack_controller_entry(fixture)
            for _ in range(num_objects)
        ]

        return [
            await create_test_agents_entry(
                fixture,
                uuid=str(uuid4()),
                rack_id=racks[i].id,
                rackcontroller_id=rack_controllers[i]["id"],
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Agent:
        rack = await create_test_rack_entry(fixture, name="rack")
        rack_controller = await create_test_rack_controller_entry(fixture)

        return await create_test_agents_entry(
            fixture,
            uuid=str(uuid4()),
            rack_id=rack.id,
            rackcontroller_id=rack_controller["id"],
        )

    @pytest.fixture
    async def instance_builder(
        self, fixture: Fixture, *args, **kwargs
    ) -> AgentBuilder:
        rack = await create_test_rack_entry(fixture, name="builder-rack")
        rack_controller = await create_test_rack_controller_entry(fixture)

        return AgentBuilder(
            uuid=str(uuid4()),
            rack_id=rack.id,
            rackcontroller_id=rack_controller["id"],
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[AgentBuilder]:
        return AgentBuilder

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> AgentsRepository:
        return AgentsRepository(Context(connection=db_connection))

    @pytest.mark.asyncio
    @pytest.mark.allow_transactions
    async def test_delete_rackcontroller_cascades_to_agents(
        self, fixture: Fixture, db_connection: AsyncConnection
    ) -> None:
        """Test that deleting a node cascades to delete associated agents."""
        # Create rack and rack controller
        rack = await create_test_rack_entry(fixture, name="test-rack")
        rack_controller = await create_test_rack_controller_entry(fixture)

        # Create agent referencing the rack controller
        agent = await create_test_agents_entry(
            fixture,
            uuid=str(uuid4()),
            rack_id=rack.id,
            rackcontroller_id=rack_controller["id"],
        )

        # Commit the fixture setup so the deferred FK check below is
        # evaluated against the deletion of the rack controller, instead
        # of being folded into the same transaction as the agent insert.
        await db_connection.commit()

        # Verify agent exists
        context = Context(connection=db_connection)
        repo = AgentsRepository(context)
        found_agent = await repo.get_by_id(agent.id)
        assert found_agent is not None

        # Delete the rack controller node
        stmt = delete(NodeTable).where(NodeTable.c.id == rack_controller["id"])
        await db_connection.execute(stmt)
        await db_connection.commit()

        # Verify agent was cascade deleted
        deleted_agent = await repo.get_by_id(agent.id)
        assert deleted_agent is None
