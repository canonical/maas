# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.agents import AgentBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.agents import (
    AgentsClauseFactory,
    AgentsRepository,
)
from maasservicelayer.models.agents import Agent
from tests.fixtures.factories.agents import create_test_agents_entry
from tests.fixtures.factories.node import create_test_rack_controller_entry
from tests.fixtures.factories.racks import create_test_rack_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestAgentsClauseFactory:
    def test_with_id(self) -> None:
        clause = AgentsClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_agent.id = 1")

    def with_rack_id(self) -> None:
        clause = AgentsClauseFactory.with_rack_id(2)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_agent.url = 2")

    def with_rack_id_in(self) -> None:
        clause = AgentsClauseFactory.with_rack_id_in({1, 2})
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_agent.id IN (1, 2)")


class TestAgentsRepository(RepositoryCommonTests[Agent]):
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
