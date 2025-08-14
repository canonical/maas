# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.agents import AgentBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.agents import AgentsRepository
from maasservicelayer.models.agents import Agent
from tests.fixtures.factories.agents import create_test_agents_entry
from tests.fixtures.factories.node import create_test_rack_controller_entry
from tests.fixtures.factories.racks import create_test_rack_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


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
                secret=f"secret-{i}",
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
            secret="secret",
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
            secret="secret",
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
