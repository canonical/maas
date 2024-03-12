from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.exceptions import NotFoundException
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolPatchRequest,
    ResourcePoolRequest,
)
from maasapiserver.v3.db.resource_pools import ResourcePoolRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.resource_pools import ResourcePool
from maasapiserver.v3.services import ResourcePoolsService
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestResourcePoolsService:
    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = datetime.utcnow()
        resource_pool = ResourcePool(
            id=1,
            name="test",
            description="description",
            created=now,
            updated=now,
        )
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.create = AsyncMock(
            return_value=resource_pool
        )
        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        request = ResourcePoolRequest(
            name=resource_pool.name, description=resource_pool.description
        )
        created_resource_pool = await resource_pools_service.create(request)
        resource_pool_repository_mock.create.assert_called_once_with(request)
        assert created_resource_pool is not None

    async def test_list(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.list = AsyncMock(
            return_value=ListResult[ResourcePool](items=[], total=0)
        )
        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        pagination_params = PaginationParams(page=1, size=1)
        resource_pools_list = await resource_pools_service.list(
            pagination_params
        )
        resource_pool_repository_mock.list.assert_called_once_with(
            pagination_params
        )
        assert resource_pools_list.total == 0
        assert resource_pools_list.items == []

    async def test_get_by_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = datetime.utcnow()
        resource_pool = ResourcePool(
            id=1,
            name="test",
            description="description",
            created=now,
            updated=now,
        )
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.find_by_id = AsyncMock(
            return_value=resource_pool
        )

        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        retrieved_resource_pool = await resource_pools_service.get_by_id(
            id=resource_pool.id
        )
        resource_pool_repository_mock.find_by_id.assert_called_once_with(
            resource_pool.id
        )
        assert retrieved_resource_pool == resource_pool

    async def test_patch_not_found(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.find_by_id = AsyncMock(return_value=None)
        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        with pytest.raises(NotFoundException):
            await resource_pools_service.patch(
                id=1000,
                patch_request=ResourcePoolPatchRequest(
                    name="name", description="description"
                ),
            )

    async def test_patch(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = datetime.utcnow()
        resource_pool = ResourcePool(
            id=1,
            name="test",
            description="description",
            created=now,
            updated=now,
        )
        patch_resource_pool = resource_pool.copy(
            update={"name": "test2", "description": "description2"}
        )
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.find_by_id = AsyncMock(
            return_value=resource_pool
        )
        resource_pool_repository_mock.update = AsyncMock(
            return_value=patch_resource_pool
        )

        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        updated_resource_pool = await resource_pools_service.patch(
            id=resource_pool.id,
            patch_request=ResourcePoolPatchRequest(
                name=patch_resource_pool.name,
                description=patch_resource_pool.description,
            ),
        )
        resource_pool_repository_mock.update.assert_called_once_with(
            patch_resource_pool
        )
        assert updated_resource_pool == patch_resource_pool
