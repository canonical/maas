# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsources import BootSourcesRepository
from maasservicelayer.models.bootsources import BootSource
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootSourceRepository(RepositoryCommonTests[BootSource]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootSource]:
        return [
            BootSource(
                **await create_test_bootsource_entry(
                    fixture,
                    url=f"http://images.maas.io/v{i}/",
                    priority=i,
                )
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootSource:
        return BootSource(
            **await create_test_bootsource_entry(
                fixture,
                url="http://images.maas.io/v1/",
                priority=100,
            )
        )

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> BootSourceBuilder:
        return BootSourceBuilder()

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootSourceBuilder]:
        return BootSourceBuilder

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootSourcesRepository:
        return BootSourcesRepository(Context(connection=db_connection))

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_by_id(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one(self, repository_instance, instance_builder):
        pass
