# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import date

import pytest

from maasservicelayer.builders.bootsourcecache import BootSourceCacheBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
    BootSourceCacheRepository,
)
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.models.bootsources import (
    BootSourceAvailableImage,
    BootSourceCacheOSRelease,
)
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

    def test_with_boot_source_ids(self) -> None:
        clause = BootSourceCacheClauseFactory.with_boot_source_ids([1, 2])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootsourcecache.boot_source_id IN (1, 2)"
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

    @pytest.mark.skip(reason="Does not apply to boot source cache")
    async def test_create_many_duplicated(
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

    async def test_get_all_available_images(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2025, month=4, day=23),
        )
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
            release="noble",
            release_title="24.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
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
            os="centos",
            release="8",
            release_title="CentOS 8",
            arch="amd64",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
        )

        all_available_images = await repository.get_all_available_images()
        assert len(all_available_images) == 5

        assert all_available_images == [
            BootSourceAvailableImage(
                "ubuntu", "noble", "24.04 LTS", "arm64", 1
            ),
            BootSourceAvailableImage(
                "ubuntu", "noble", "24.04 LTS", "amd64", 1
            ),
            BootSourceAvailableImage(
                "ubuntu", "focal", "20.04 LTS", "arm64", 1
            ),
            BootSourceAvailableImage(
                "ubuntu", "focal", "20.04 LTS", "amd64", 1
            ),
            BootSourceAvailableImage("centos", "8", "CentOS 8", "amd64", 1),
        ]

    async def test_get_all_available_images_ensure_grouping(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
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
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="hwe-p",
            support_eol=date(year=2025, month=4, day=23),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="hwe-s",
            support_eol=date(year=2025, month=4, day=23),
        )
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
            release="noble",
            release_title="24.04 LTS",
            arch="amd64",
            subarch="ga-24.04",
            support_eol=date(year=2029, month=5, day=31),
        )

        all_available_images = await repository.get_all_available_images()
        assert len(all_available_images) == 2

        assert all_available_images == [
            BootSourceAvailableImage(
                "ubuntu", "noble", "24.04 LTS", "amd64", 1
            ),
            BootSourceAvailableImage(
                "ubuntu", "focal", "20.04 LTS", "amd64", 1
            ),
        ]

    async def test_list_boot_source_cache_available_images(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2025, month=4, day=23),
        )
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
            os="centos",
            release="8",
            release_title="CentOS 8",
            arch="amd64",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="noble",
            release_title="24.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
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
            boot_source_id=2,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2025, month=4, day=23),
        )

        pages = 3
        page_size = 2
        num_objects = 5

        boot_source_id = 1

        expected_page_items = {
            1: [
                BootSourceAvailableImage(
                    "ubuntu", "noble", "24.04 LTS", "arm64", 1
                ),
                BootSourceAvailableImage(
                    "ubuntu", "noble", "24.04 LTS", "amd64", 1
                ),
            ],
            2: [
                BootSourceAvailableImage(
                    "ubuntu", "focal", "20.04 LTS", "arm64", 1
                ),
                BootSourceAvailableImage(
                    "ubuntu", "focal", "20.04 LTS", "amd64", 1
                ),
            ],
            3: [
                BootSourceAvailableImage(
                    "centos", "8", "CentOS 8", "amd64", 1
                ),
            ],
        }

        for page in range(1, pages + 1):
            boot_source_available_images_page = (
                await repository.list_boot_source_cache_available_images(
                    page=page, size=page_size, boot_source_id=boot_source_id
                )
            )

            if page == pages:  # last page may have fewer elements
                elements_count = page_size - (
                    (pages * page_size) % num_objects
                )
                assert (
                    len(boot_source_available_images_page.items)
                    == elements_count
                )
                for idx, expected_result in enumerate(
                    expected_page_items[page]
                ):
                    assert (
                        expected_result
                        == boot_source_available_images_page.items[idx]
                    )
            else:
                assert (
                    len(boot_source_available_images_page.items) == page_size
                )
                for idx, expected_result in enumerate(
                    expected_page_items[page]
                ):
                    assert (
                        expected_result
                        == boot_source_available_images_page.items[idx]
                    )

    async def test_list_boot_source_cache_available_images_ensure_grouping(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
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
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="hwe-p",
            support_eol=date(year=2025, month=4, day=23),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="hwe-s",
            support_eol=date(year=2025, month=4, day=23),
        )
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
            release="noble",
            release_title="24.04 LTS",
            arch="amd64",
            subarch="ga-24.04",
            support_eol=date(year=2029, month=5, day=31),
        )

        page_size = 2
        expected_num_objects = 2

        boot_source_id = 1

        expected_page_items = [
            BootSourceAvailableImage(
                "ubuntu", "noble", "24.04 LTS", "amd64", 1
            ),
            BootSourceAvailableImage(
                "ubuntu", "focal", "20.04 LTS", "amd64", 1
            ),
        ]

        boot_source_available_images_page = (
            await repository.list_boot_source_cache_available_images(
                page=1, size=page_size, boot_source_id=boot_source_id
            )
        )

        assert boot_source_available_images_page.total == expected_num_objects
        assert len(boot_source_available_images_page.items) == page_size
        for idx, expected_result in enumerate(expected_page_items):
            assert (
                expected_result == boot_source_available_images_page.items[idx]
            )

    async def test_list_unique_os_releases(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
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
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="hwe-p",
            support_eol=date(year=2025, month=4, day=23),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="focal",
            release_title="20.04 LTS",
            arch="amd64",
            subarch="hwe-s",
            support_eol=date(year=2025, month=4, day=23),
        )
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
            release="noble",
            release_title="24.04 LTS",
            arch="amd64",
            subarch="ga-24.04",
            support_eol=date(year=2029, month=5, day=31),
        )

        result = await repository.get_unique_os_releases()

        assert len(result) == 2
        assert BootSourceCacheOSRelease(os="ubuntu", release="focal") in result
        assert BootSourceCacheOSRelease(os="ubuntu", release="noble") in result

    async def test_get_supported_arches(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
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
            release="focal",
            release_title="20.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2025, month=4, day=23),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="noble",
            release_title="24.04 LTS",
            arch="ppc64el",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
        )

        result = await repository.get_supported_arches()

        assert set(result) == {"amd64", "arm64", "ppc64el"}

    async def test_get_supported_arches__filtered(
        self, fixture: Fixture, repository: BootSourceCacheRepository
    ) -> None:
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
            release="focal",
            release_title="20.04 LTS",
            arch="arm64",
            subarch="generic",
            support_eol=date(year=2025, month=4, day=23),
        )
        await create_test_bootsourcecache_entry(
            fixture,
            boot_source_id=1,
            os="ubuntu",
            release="noble",
            release_title="24.04 LTS",
            arch="ppc64el",
            subarch="generic",
            support_eol=date(year=2029, month=5, day=31),
        )

        result = await repository.get_supported_arches(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_os("ubuntu"),
                        BootSourceCacheClauseFactory.with_release("focal"),
                    ]
                )
            )
        )

        assert set(result) == {"amd64", "arm64"}
