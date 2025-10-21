# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
    BootSourcesRepository,
)
from maasservicelayer.models.bootsources import BootSource
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootSourcesClauseFactory:
    def test_with_id(self) -> None:
        clause = BootSourcesClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsource.id = 1")

    def test_with_url(self) -> None:
        clause = BootSourcesClauseFactory.with_url("http://foo.com")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsource.url = 'http://foo.com'")

    def test_with_ids(self) -> None:
        clause = BootSourcesClauseFactory.with_ids({1, 2})
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsource.id IN (1, 2)")


class TestBootSourcesRepository(RepositoryCommonTests[BootSource]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootSource]:
        return [
            await create_test_bootsource_entry(
                fixture,
                url=f"http://images.maas.io/v{i}/",
                priority=i,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootSource:
        return await create_test_bootsource_entry(
            fixture,
            url="http://images.maas.io/v1/",
            priority=100,
        )

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> BootSourceBuilder:
        return BootSourceBuilder(
            url="http://example.com/v10/",
            keyring_filename="/path/to/file.gpg",
            keyring_data=b"",
            priority=10,
            skip_keyring_verification=False,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootSourceBuilder]:
        return BootSourceBuilder

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootSourcesRepository:
        return BootSourcesRepository(Context(connection=db_connection))
