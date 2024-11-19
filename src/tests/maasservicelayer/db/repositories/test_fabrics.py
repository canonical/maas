# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.fabrics import FabricsRepository
from maasservicelayer.models.fabrics import Fabric
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestFabricsRepository(RepositoryCommonTests[Fabric]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> FabricsRepository:
        return FabricsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Fabric]:
        created_fabrics = [
            await create_test_fabric_entry(
                fixture, name=str(i), description=str(i)
            )
            for i in range(num_objects)
        ]
        return created_fabrics

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Fabric:
        return await create_test_fabric_entry(
            fixture, name=str("myfabric"), description=str("description")
        )
