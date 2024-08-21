from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.exceptions import NotFoundException
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolRequest,
    ResourcePoolUpdateRequest,
)
from maasapiserver.v3.db.resource_pools import ResourcePoolRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.resource_pools import ResourcePool
from maasapiserver.v3.services import ResourcePoolsService


@pytest.mark.asyncio
class TestResourcePoolsService:
    async def test_create(self) -> None:
        db_connection = Mock(AsyncConnection)
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
        assert (
            resource_pool_repository_mock.create.mock_calls[0]
            .args[0]
            .get_values()["name"]
            == "test"
        )
        assert (
            resource_pool_repository_mock.create.mock_calls[0]
            .args[0]
            .get_values()["description"]
            == "description"
        )
        assert created_resource_pool is not None

    async def test_list(self) -> None:
        db_connection = Mock(AsyncConnection)
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.list = AsyncMock(
            return_value=ListResult[ResourcePool](items=[], next_token=None)
        )
        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        resource_pools_list = await resource_pools_service.list(
            token=None, size=1
        )
        resource_pool_repository_mock.list.assert_called_once_with(
            token=None, size=1
        )
        assert resource_pools_list.next_token is None
        assert resource_pools_list.items == []

    async def test_get_by_id(self) -> None:
        db_connection = Mock(AsyncConnection)
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

    async def test_patch_not_found(self) -> None:
        db_connection = Mock(AsyncConnection)
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.update = AsyncMock(
            side_effect=NotFoundException()
        )
        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        with pytest.raises(NotFoundException):
            await resource_pools_service.update(
                id=1000,
                patch_request=ResourcePoolUpdateRequest(
                    name="name", description="description"
                ),
            )

    async def test_update(self) -> None:
        db_connection = Mock(AsyncConnection)
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
        updated_resource_pool = await resource_pools_service.update(
            id=resource_pool.id,
            patch_request=ResourcePoolUpdateRequest(
                name=patch_resource_pool.name,
                description=patch_resource_pool.description,
            ),
        )
        assert (
            resource_pool_repository_mock.update.mock_calls[0].args[0]
            == resource_pool.id
        )
        assert (
            resource_pool_repository_mock.update.mock_calls[0]
            .args[1]
            .get_values()["name"]
            == patch_resource_pool.name
        )
        assert (
            resource_pool_repository_mock.update.mock_calls[0]
            .args[1]
            .get_values()["description"]
            == patch_resource_pool.description
        )
        assert updated_resource_pool == patch_resource_pool
