#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolClauseFactory,
    ResourcePoolRepository,
    ResourcePoolResourceBuilder,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    NotFoundException,
)
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.resource_pools import (
    create_n_test_resource_pools,
    create_test_resource_pool,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestResourcePoolCreateOrUpdateResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            ResourcePoolResourceBuilder()
            .with_name("test")
            .with_description("descr")
            .with_created(now)
            .with_updated(now)
            .build()
        )

        assert resource.get_values() == {
            "name": "test",
            "description": "descr",
            "created": now,
            "updated": now,
        }


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


class TestResourcePoolRepo(RepositoryCommonTests[ResourcePool]):
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
    async def _created_instance(self, fixture: Fixture) -> ResourcePool:
        return await create_test_resource_pool(fixture)

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


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestResourcePoolRepository:
    async def test_list_with_query(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        resource_pools = await create_n_test_resource_pools(fixture, size=5)
        resource_pools_repository = ResourcePoolRepository(
            Context(connection=db_connection)
        )
        selected_ids = [resource_pools[0].id, resource_pools[1].id]
        retrieved_resource_pools = await resource_pools_repository.list(
            token=None,
            size=20,
            query=QuerySpec(
                where=ResourcePoolClauseFactory.with_ids(selected_ids)
            ),
        )
        assert len(retrieved_resource_pools.items) == 2
        assert all(
            resource_pool.id in selected_ids
            for resource_pool in retrieved_resource_pools.items
        )

    async def test_create(self, db_connection: AsyncConnection) -> None:
        now = utcnow()
        resource_pools_repository = ResourcePoolRepository(
            Context(connection=db_connection)
        )
        created_resource_pools = await resource_pools_repository.create(
            ResourcePoolResourceBuilder()
            .with_name("my_resource_pool")
            .with_description("my description")
            .with_created(now)
            .with_updated(now)
            .build()
        )
        assert created_resource_pools.id
        assert created_resource_pools.name == "my_resource_pool"
        assert created_resource_pools.description == "my description"
        assert created_resource_pools.created.astimezone(
            timezone.utc
        ) >= now.astimezone(timezone.utc)
        assert created_resource_pools.updated.astimezone(
            timezone.utc
        ) >= now.astimezone(timezone.utc)

    async def test_create_duplicated(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        resource_pools_repository = ResourcePoolRepository(
            Context(connection=db_connection)
        )
        created_resource_pools = await create_test_resource_pool(fixture)

        with pytest.raises(AlreadyExistsException):
            await resource_pools_repository.create(
                ResourcePoolResourceBuilder()
                .with_name(created_resource_pools.name)
                .with_description(created_resource_pools.description)
                .with_created(now)
                .with_updated(now)
                .build()
            )

    async def test_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        resource_pools_repository = ResourcePoolRepository(
            Context(connection=db_connection)
        )
        created_resource_pool = await create_test_resource_pool(fixture)
        now = utcnow()
        updated_resource = (
            ResourcePoolResourceBuilder()
            .with_name("new name")
            .with_description("new description")
            .with_updated(now)
            .build()
        )
        updated_pools = await resource_pools_repository.update_by_id(
            created_resource_pool.id, updated_resource
        )
        # unchanged
        assert updated_pools.id == created_resource_pool.id
        assert updated_pools.created == created_resource_pool.created
        # changed
        assert updated_pools.name == "new name"
        assert updated_pools.description == "new description"
        assert updated_pools.updated > created_resource_pool.updated

    async def test_update_duplicated_name(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        resource_pools_repository = ResourcePoolRepository(
            Context(connection=db_connection)
        )
        created_resource_pool = await create_test_resource_pool(
            fixture, name="test1"
        )
        created_resource_pool2 = await create_test_resource_pool(
            fixture, name="test2"
        )

        now = utcnow()
        updated_resource = (
            ResourcePoolResourceBuilder()
            .with_name(created_resource_pool.name)
            .with_updated(now)
            .build()
        )

        with pytest.raises(AlreadyExistsException):
            await resource_pools_repository.update_by_id(
                created_resource_pool2.id, updated_resource
            )

    async def test_update_nonexistent(
        self, db_connection: AsyncConnection
    ) -> None:
        now = utcnow()
        resource_pools_repository = ResourcePoolRepository(
            Context(connection=db_connection)
        )
        resource = (
            ResourcePoolResourceBuilder()
            .with_name("test")
            .with_description("test")
            .with_updated(now)
            .build()
        )
        with pytest.raises(NotFoundException):
            await resource_pools_repository.update_by_id(1000, resource)
