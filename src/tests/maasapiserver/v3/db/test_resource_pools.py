from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.exceptions import AlreadyExistsException
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolRequest,
)
from maasapiserver.v3.db.resource_pools import ResourcePoolRepository
from maasapiserver.v3.models.resource_pools import ResourcePool
from tests.fixtures.factories.resource_pools import (
    create_n_test_resource_pools,
    create_test_resource_pool,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestResourcePoolRepo(RepositoryCommonTests[ResourcePool]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ResourcePoolRepository:
        return ResourcePoolRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[ResourcePool], int]:
        resource_pools_count = 10
        # The "default" resource pool with id=0 is created at startup with the migrations.
        # By consequence, we create resource_pools_count-1 resource pools here.
        created_resource_pools = (
            await create_n_test_resource_pools(
                fixture, size=resource_pools_count - 1
            )
        )[::-1]
        return created_resource_pools, resource_pools_count

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> ResourcePool:
        return await create_test_resource_pool(fixture)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestResourcePoolRepository:
    async def test_create(self, db_connection: AsyncConnection) -> None:
        now = datetime.utcnow()
        resource_pools_repository = ResourcePoolRepository(db_connection)
        created_resource_pools = await resource_pools_repository.create(
            ResourcePoolRequest(
                name="my_resource_pool", description="my description"
            )
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
        resource_pools_repository = ResourcePoolRepository(db_connection)
        created_resource_pools = await create_test_resource_pool(fixture)

        with pytest.raises(AlreadyExistsException):
            await resource_pools_repository.create(
                ResourcePoolRequest(
                    name=created_resource_pools.name,
                    description=created_resource_pools.description,
                )
            )

    async def test_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        resource_pools_repository = ResourcePoolRepository(db_connection)
        created_resource_pool = await create_test_resource_pool(fixture)
        updated_request = created_resource_pool.copy()
        updated_request.name = "new name"
        updated_request.description = "new description"
        updated_pools = await resource_pools_repository.update(updated_request)
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
        resource_pools_repository = ResourcePoolRepository(db_connection)
        created_resource_pool = await create_test_resource_pool(
            fixture, name="test1"
        )
        created_resource_pool2 = await create_test_resource_pool(
            fixture, name="test2"
        )

        updated_resource_pool = created_resource_pool.copy(
            update={"id": created_resource_pool2.id}
        )
        with pytest.raises(AlreadyExistsException):
            await resource_pools_repository.update(updated_resource_pool)

    async def test_update_nonexistent(
        self, db_connection: AsyncConnection
    ) -> None:
        now = datetime.utcnow()
        resource_pools_repository = ResourcePoolRepository(db_connection)
        resource_pool = ResourcePool(
            id=1000, name="test", description="test", created=now, updated=now
        )

        with pytest.raises(NoResultFound):
            await resource_pools_repository.update(resource_pool)
