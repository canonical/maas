# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.fabrics import FabricsRepository
from maasapiserver.v3.models.fabrics import Fabric
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestFabricsRepository(RepositoryCommonTests[Fabric]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> FabricsRepository:
        return FabricsRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Fabric], int]:
        fabrics_count = 10
        created_fabrics = [
            await create_test_fabric_entry(
                fixture, name=str(i), description=str(i)
            )
            for i in range(fabrics_count)
        ][::-1]
        return created_fabrics, fabrics_count

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Fabric:
        return await create_test_fabric_entry(
            fixture, name=str("myfabric"), description=str("description")
        )
