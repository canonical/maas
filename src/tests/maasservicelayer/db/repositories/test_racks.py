# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.racks import RackBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.racks import RacksRepository
from maasservicelayer.models.racks import Rack
from tests.fixtures.factories.racks import create_test_rack_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestRacksRepository(RepositoryCommonTests[Rack]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Rack]:
        return [
            await create_test_rack_entry(
                fixture,
                name=f"rack{i}",
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Rack:
        return await create_test_rack_entry(
            fixture,
            name="rack-8",
        )

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> RackBuilder:
        return RackBuilder(name="rack-8")

    @pytest.fixture
    async def instance_builder_model(self) -> type[RackBuilder]:
        return RackBuilder

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> RacksRepository:
        return RacksRepository(Context(connection=db_connection))
