# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.bootresourcesets import BootResourceSetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
    BootResourceSetsRepository,
)
from maasservicelayer.models.bootresourcesets import BootResourceSet
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootResourceSetClauseFactory:
    def with_resource_id(self) -> None:
        clause = BootResourceSetClauseFactory.with_resource_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootresourceset.resource_id = 1"
        )

    def with_version(self) -> None:
        clause = BootResourceSetClauseFactory.with_version("20250618")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootresourceset.version = '20250618'"
        )


class TestBootResourceSetRepository(RepositoryCommonTests[BootResourceSet]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootResourceSet]:
        return [
            await create_test_bootresourceset_entry(
                fixture,
                version=f"20250618.{i}",
                label="stable",
                resource_id=1,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootResourceSet:
        return await create_test_bootresourceset_entry(
            fixture,
            version="20250618",
            label="stable",
            resource_id=1,
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootResourceSetBuilder:
        return BootResourceSetBuilder(
            version="20250618",
            label="stable",
            resource_id=1,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootResourceSetBuilder]:
        return BootResourceSetBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootResourceSetsRepository:
        return BootResourceSetsRepository(Context(connection=db_connection))
