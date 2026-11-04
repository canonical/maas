# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.builders.bootresourcesets import BootResourceSetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetsRepository,
)
from maasservicelayer.filters.bootresourcesets import (
    BootResourceSetFilters,
    BootResourceSetsOrdering,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.bootresourcesets import BootResourceSet
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestCommonBootResourceSetRepository(
    RepositoryCommonTests[BootResourceSet]
):
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


class TestBootResourceSetRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> BootResourceSetsRepository:
        return BootResourceSetsRepository(Context(connection=db_connection))

    async def test_domain_version_prefix_and_ordering(
        self, fixture, repository
    ):
        sets = []
        for version in ["20261029.1", "20261029.2", "20261030.1"]:
            sets.append(
                await create_test_bootresourceset_entry(
                    fixture,
                    version=version,
                    label="stable",
                    resource_id=1,
                )
            )
        result = await repository.get_many(
            QuerySpec(
                where=BootResourceSetFilters.with_version_prefix("20261029"),
                order_by=(
                    BootResourceSetsOrdering.desc(
                        BootResourceSetsOrdering.by_id()
                    ),
                ),
            )
        )
        assert result == list(reversed(sets[:2]))

    async def test_get_latest_for_boot_resource(
        self,
        fixture: Fixture,
        repository: BootResourceSetsRepository,
    ) -> None:
        boot_resource = await create_test_bootresource_entry(
            fixture,
            name="ubuntu/noble",
            architecture="amd64/generic",
            rtype=BootResourceType.SYNCED,
        )
        await create_test_bootresourceset_entry(
            fixture,
            version="20220202",
            label="stable",
            resource_id=boot_resource.id,
        )
        last = await create_test_bootresourceset_entry(
            fixture,
            version="20240404",
            label="stable",
            resource_id=boot_resource.id,
        )

        resource_set = await repository.get_latest_for_boot_resource(
            boot_resource.id
        )

        assert resource_set == last

    async def test_get_latest_for_boot_resource_no_sets(
        self,
        fixture: Fixture,
        repository: BootResourceSetsRepository,
    ) -> None:
        boot_resource = await create_test_bootresource_entry(
            fixture,
            name="ubuntu/noble",
            architecture="amd64/generic",
            rtype=BootResourceType.SYNCED,
        )

        resource_set = await repository.get_latest_for_boot_resource(
            boot_resource.id
        )

        assert resource_set is None

    async def test_get_many_newest_to_oldest_for_boot_resource(
        self,
        fixture: Fixture,
        repository: BootResourceSetsRepository,
    ) -> None:
        boot_resource = await create_test_bootresource_entry(
            fixture,
            name="ubuntu/noble",
            architecture="amd64/generic",
            rtype=BootResourceType.SYNCED,
        )
        first = await create_test_bootresourceset_entry(
            fixture,
            version="20220202",
            label="stable",
            resource_id=boot_resource.id,
        )
        second = await create_test_bootresourceset_entry(
            fixture,
            version="20240404",
            label="stable",
            resource_id=boot_resource.id,
        )

        resource_sets = (
            await repository.get_many_newest_to_oldest_for_boot_resource(
                boot_resource.id
            )
        )

        assert resource_sets == [second, first]

    async def test_get_many_newest_to_oldest_for_boot_resource_no_sets(
        self,
        fixture: Fixture,
        repository: BootResourceSetsRepository,
    ) -> None:
        boot_resource = await create_test_bootresource_entry(
            fixture,
            name="ubuntu/noble",
            architecture="amd64/generic",
            rtype=BootResourceType.SYNCED,
        )

        resource_sets = (
            await repository.get_many_newest_to_oldest_for_boot_resource(
                boot_resource.id
            )
        )

        assert resource_sets == []
