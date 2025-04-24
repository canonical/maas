# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.discoveries import DiscoveriesRepository
from maasservicelayer.models.discoveries import Discovery
from tests.fixtures.factories.discoveries import create_test_discovery
from tests.fixtures.factories.node import create_test_rack_controller_entry
from tests.maasservicelayer.db.repositories.base import (
    Fixture,
    ReadOnlyRepositoryCommonTests,
)


class TestDiscoveriesRepository(ReadOnlyRepositoryCommonTests[Discovery]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> DiscoveriesRepository:
        return DiscoveriesRepository(context=Context(connection=db_connection))

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Discovery:
        return await create_test_discovery(fixture, hostname="foo")

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Discovery]:
        rack_controller = await create_test_rack_controller_entry(fixture)
        return [
            await create_test_discovery(
                fixture, hostname=f"host-{i}", rack_controller=rack_controller
            )
            for i in range(num_objects)
        ]
