# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import date

import pytest

from maasservicelayer.builders.bootsourcecache import BootSourceCacheBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
    BootSourceCacheRepository,
)
from maasservicelayer.models.bootsourcecache import BootSourceCache
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.fixtures.factories.bootsourcecache import (
    create_test_bootsourcecache_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests
from tests.maasservicelayer.db.repositories.test_bootsources import (
    AsyncConnection,
)


class TestBootSourceCacheClauseFactory:
    def test_with_os(self) -> None:
        clause = BootSourceCacheClauseFactory.with_os("ubuntu")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.os = 'ubuntu'"
        )

    def test_with_arch(self) -> None:
        clause = BootSourceCacheClauseFactory.with_arch("amd64")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.arch = 'amd64'"
        )

    def test_with_subarch(self) -> None:
        clause = BootSourceCacheClauseFactory.with_subarch("generic")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.subarch = 'generic'"
        )

    def test_with_release(self) -> None:
        clause = BootSourceCacheClauseFactory.with_release("noble")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.release = 'noble'"
        )

    def test_with_label(self) -> None:
        clause = BootSourceCacheClauseFactory.with_label("candidate")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.label = 'candidate'"
        )

    def test_with_kflavor(self) -> None:
        clause = BootSourceCacheClauseFactory.with_kflavor("lowlatency")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.kflavor = 'lowlatency'"
        )

    def test_with_boot_source_id(self) -> None:
        clause = BootSourceCacheClauseFactory.with_boot_source_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.boot_source_id = 1"
        )

    def test_with_ids(self) -> None:
        clause = BootSourceCacheClauseFactory.with_ids({1, 2})
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.id IN (1, 2)"
        )


class TestCommonBootSourceCacheRepository(
    RepositoryCommonTests[BootSourceCache]
):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootSourceCache]:
        boot_source = await create_test_bootsource_entry(
            fixture, url="http://images.maas.io/", priority=1
        )

        return [
            await create_test_bootsourcecache_entry(
                fixture,
                boot_source_id=boot_source.id,
                os=f"ubuntu-{i}",
                arch="amd64",
                subarch="generic",
                release="noble",
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootSourceCache:
        boot_source = await create_test_bootsource_entry(
            fixture, url="http://images.maas.io/", priority=1
        )
        return await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=boot_source.id,
            os="ubuntu",
            arch="amd64",
            subarch="generic",
            release="noble",
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootSourceCacheBuilder:
        return BootSourceCacheBuilder(
            os="ubuntu",
            boot_source_id=1,
            arch="amd64",
            subarch="generic",
            release="jammy",
            label="stable",
            extra={},
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootSourceCacheBuilder]:
        return BootSourceCacheBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BaseRepository:
        return BootSourceCacheRepository(Context(connection=db_connection))

    @pytest.mark.skip(reason="Does not apply to boot source cache")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()


class TestBootSourceCacheRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> BootSourceCacheRepository:
        return BootSourceCacheRepository(Context(connection=db_connection))

    async def test_get_available_lts_releases(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="noble",
            release_title="24.04 LTS",
            arch="amd64",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="jammy",
            release_title="22.04 LTS",
            arch="amd64",
            subarch="generic",
            support_eol=date(year=2027, month=4, day=21),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="generic",
            support_eol=date(year=2025, month=4, day=23),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="plucky",
            release_title="25.04",
            arch="amd64",
            subarch="generic",
            support_eol=date(year=2026, month=1, day=15),
        )
        releases = await repository.get_available_lts_releases()
        assert releases == ["noble", "jammy", "focal"]
