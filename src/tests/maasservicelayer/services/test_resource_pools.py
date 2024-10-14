#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolCreateOrUpdateResourceBuilder,
    ResourcePoolRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services import ResourcePoolsService


@pytest.mark.asyncio
class TestResourcePoolsService:
    async def test_create(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = datetime.now(timezone.utc)
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
        resource = (
            ResourcePoolCreateOrUpdateResourceBuilder()
            .with_name(resource_pool.name)
            .with_description(resource_pool.description)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        created_resource_pool = await resource_pools_service.create(resource)
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
            token=None, size=1, query=None
        )
        resource_pool_repository_mock.list.assert_called_once_with(
            token=None, size=1, query=None
        )
        assert resource_pools_list.next_token is None
        assert resource_pools_list.items == []

    async def test_list_ids(self) -> None:
        db_connection = Mock(AsyncConnection)
        resource_pool_repository_mock = Mock(ResourcePoolRepository)
        resource_pool_repository_mock.list_ids = AsyncMock(
            return_value={1, 2, 3}
        )
        resource_pools_service = ResourcePoolsService(
            connection=db_connection,
            resource_pools_repository=resource_pool_repository_mock,
        )
        ids_list = await resource_pools_service.list_ids()
        resource_pool_repository_mock.list_ids.assert_called_once()
        assert ids_list == {1, 2, 3}

    async def test_get_by_id(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = datetime.now(timezone.utc)
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
                resource=ResourcePoolCreateOrUpdateResourceBuilder()
                .with_name("name")
                .with_description("description")
                .build(),
            )

    async def test_update(self) -> None:
        db_connection = Mock(AsyncConnection)
        now = datetime.now(timezone.utc)
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
            resource=ResourcePoolCreateOrUpdateResourceBuilder()
            .with_name(patch_resource_pool.name)
            .with_description(patch_resource_pool.description)
            .build(),
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
