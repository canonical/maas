# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.models.bootresources import BootResource
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootResourceClauseFactory:
    def test_with_name(self) -> None:
        clause = BootResourceClauseFactory.with_name("ubuntu/noble")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.name = 'ubuntu/noble'")

    def test_with_architecture(self) -> None:
        clause = BootResourceClauseFactory.with_architecture("amd64/generic")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.architecture = 'amd64/generic'")

    def test_with_alias(self) -> None:
        clause = BootResourceClauseFactory.with_alias("ubuntu/24.04")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.alias = 'ubuntu/24.04'")

    def test_with_rtype(self) -> None:
        clause = BootResourceClauseFactory.with_rtype(BootResourceType.SYNCED)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.rtype = 0")

    def test_with_ids(self) -> None:
        clause = BootResourceClauseFactory.with_ids({1, 2, 3})
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.id IN (1, 2, 3)")


class TestBootResourceRepository(RepositoryCommonTests[BootResource]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootResource]:
        return [
            await create_test_bootresource_entry(
                fixture,
                rtype=BootResourceType.SYNCED,
                name=f"ubuntu/noble-{i}",
                architecture="amd64/generic",
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootResource:
        return await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/generic",
        )

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> BootResourceBuilder:
        return BootResourceBuilder(
            rtype=BootResourceType.SYNCED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            rolling=False,
            base_image="",
            extra={},
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootResourceBuilder]:
        return BootResourceBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootResourcesRepository:
        return BootResourcesRepository(Context(connection=db_connection))

    @pytest.mark.skip(reason="Doesn't apply to boot resources")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()
