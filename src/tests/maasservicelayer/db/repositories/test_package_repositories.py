# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.package_repositories import (
    PACKAGE_REPO_MAIN_ARCHES,
    PACKAGE_REPO_PORTS_ARCHES,
)
from maasservicelayer.builders.package_repositories import (
    PackageRepositoryBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.package_repositories import (
    PackageRepositoriesRepository,
)
from maasservicelayer.models.fields import PackageRepoUrl
from maasservicelayer.models.package_repositories import PackageRepository
from tests.fixtures.factories.package_repositories import (
    create_test_package_repository,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestCommonPackageRepositoriesRepository(
    RepositoryCommonTests[PackageRepository]
):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> PackageRepositoriesRepository:
        return PackageRepositoriesRepository(
            context=Context(connection=db_connection)
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[PackageRepository]:
        # The default package repositories are created by the migration and it
        # has the following timestamp hardcoded in the test sql dump,
        # see src/maasserver/testing/inital.maas_test.sql:12541
        ts = datetime(2021, 11, 19, 12, 40, 50, 636477, tzinfo=timezone.utc)
        created_package_repositories = [
            PackageRepository(
                id=1,
                created=ts,
                updated=ts,
                name="main_archive",
                url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
                components=set(),
                arches=PACKAGE_REPO_MAIN_ARCHES,
                key="",
                default=True,
                enabled=True,
                disabled_pockets=set(),
                distributions=[],
                disabled_components=set(),
                disable_sources=True,
            ),
            PackageRepository(
                id=2,
                created=ts,
                updated=ts,
                name="ports_archive",
                url=PackageRepoUrl("http://ports.ubuntu.com/ubuntu-ports"),
                components=set(),
                arches=PACKAGE_REPO_PORTS_ARCHES,
                key="",
                default=True,
                enabled=True,
                disabled_pockets=set(),
                distributions=[],
                disabled_components=set(),
                disable_sources=True,
            ),
        ]
        created_package_repositories.extend(
            [
                await create_test_package_repository(
                    fixture, name=f"test-{i}", default=False
                )
                for i in range(num_objects - 2)
            ]
        )
        return created_package_repositories

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> PackageRepository:
        return await create_test_package_repository(fixture)

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> PackageRepositoryBuilder:
        return PackageRepositoryBuilder(
            name="test-main",
            key="test-key",
            url=PackageRepoUrl("http://archive.ubuntu.com/ubuntu"),
            distributions=[],
            components=set(),
            arches=set(),
            disabled_pockets=set(),
            disabled_components=set(),
            disable_sources=False,
            default=False,
            enabled=True,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[PackageRepositoryBuilder]:
        return PackageRepositoryBuilder


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestPackageRepositoriesRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> PackageRepositoriesRepository:
        return PackageRepositoriesRepository(
            context=Context(connection=db_connection)
        )

    async def test_get_main_archive(
        self, repository: PackageRepositoriesRepository
    ) -> None:
        main_archive = await repository.get_main_archive()
        assert main_archive is not None
        assert main_archive.name == "main_archive"

    async def test_get_ports_archive(
        self, repository: PackageRepositoriesRepository
    ) -> None:
        ports_archive = await repository.get_ports_archive()
        assert ports_archive is not None
        assert ports_archive.name == "ports_archive"
