# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.resource_pools import ResourcePoolBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolClauseFactory,
    ResourcePoolRepository,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    NotFoundException,
)
from maasservicelayer.models.resource_pools import ResourcePool
from tests.fixtures.factories.resource_pools import (
    create_n_test_resource_pools,
    create_test_resource_pool,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestResourcePoolClauseFactory:
    def test_builder(self) -> None:
        clause = ResourcePoolClauseFactory.with_ids([])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_resourcepool.id IN (NULL) AND (1 != 1)")

        clause = ResourcePoolClauseFactory.with_ids([1, 2, 3])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_resourcepool.id IN (1, 2, 3)")


class TestResourcePoolRepository(RepositoryCommonTests[ResourcePool]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ResourcePoolRepository:
        return ResourcePoolRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[ResourcePool]:
        # The default resource pool is created by the migrations
        # and it has the following timestamp hardcoded in the test sql dump,
        # see src/maasserver/testing/inital.maas_test.sql:12611
        ts = datetime(2021, 11, 19, 12, 40, 56, 904770, tzinfo=timezone.utc)
        created_resource_pools = [
            ResourcePool(
                id=0,
                name="default",
                description="Default pool",
                created=ts,
                updated=ts,
            )
        ]
        created_resource_pools.extend(
            await create_n_test_resource_pools(fixture, size=num_objects - 1)
        )
        return created_resource_pools

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> ResourcePool:
        return await create_test_resource_pool(fixture)

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourcePoolBuilder]:
        return ResourcePoolBuilder

    @pytest.fixture
    async def instance_builder(self) -> ResourcePoolBuilder:
        return ResourcePoolBuilder(name="test", description="descr")

    @pytest.mark.parametrize("num_objects", [10])
    async def list_ids(
        self,
        repository_instance: ResourcePoolRepository,
        _setup_test_list: list[ResourcePool],
    ) -> None:
        resource_pools = _setup_test_list
        ids = await repository_instance.list_ids()
        for rp in resource_pools:
            assert rp.id in ids
        assert len(ids) == len(resource_pools)

    async def test_list_with_query(
        self, repository_instance: ResourcePoolRepository, fixture: Fixture
    ) -> None:
        resource_pools = await create_n_test_resource_pools(fixture, size=5)
        selected_ids = [resource_pools[0].id, resource_pools[1].id]
        retrieved_resource_pools = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(
                where=ResourcePoolClauseFactory.with_ids(selected_ids)
            ),
        )
        assert len(retrieved_resource_pools.items) == 2
        assert retrieved_resource_pools.total == 2
        assert all(
            resource_pool.id in selected_ids
            for resource_pool in retrieved_resource_pools.items
        )

    async def test_update_duplicated_name(
        self, repository_instance: ResourcePoolRepository, fixture: Fixture
    ) -> None:
        created_resource_pool = await create_test_resource_pool(
            fixture, name="test1"
        )
        created_resource_pool2 = await create_test_resource_pool(
            fixture, name="test2"
        )

        updated_resource = ResourcePoolBuilder(name=created_resource_pool.name)

        with pytest.raises(AlreadyExistsException):
            await repository_instance.update_by_id(
                created_resource_pool2.id, updated_resource
            )

    async def test_update_nonexistent(
        self, repository_instance: ResourcePoolRepository
    ) -> None:
        builder = ResourcePoolBuilder(name="test", description="test")
        with pytest.raises(NotFoundException):
            await repository_instance.update_by_id(1000, builder)
