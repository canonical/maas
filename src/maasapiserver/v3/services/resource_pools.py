from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolRequest,
    ResourcePoolUpdateRequest,
)
from maasapiserver.v3.db.resource_pools import (
    ResourcePoolCreateOrUpdateResourceBuilder,
    ResourcePoolRepository,
)
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.resource_pools import ResourcePool


class ResourcePoolsService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        resource_pools_repository: Optional[ResourcePoolRepository] = None,
    ):
        super().__init__(connection)
        self.resource_pools_repository = (
            resource_pools_repository or ResourcePoolRepository(connection)
        )

    async def create(
        self, resource_pool_request: ResourcePoolRequest
    ) -> ResourcePool:
        now = utcnow()
        resource = (
            ResourcePoolCreateOrUpdateResourceBuilder()
            .with_name(resource_pool_request.name)
            .with_description(resource_pool_request.description)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        return await self.resource_pools_repository.create(resource)

    async def get_by_id(self, id: int) -> Optional[ResourcePool]:
        return await self.resource_pools_repository.find_by_id(id)

    async def list(
        self, token: str | None, size: int
    ) -> ListResult[ResourcePool]:
        return await self.resource_pools_repository.list(
            token=token, size=size
        )

    async def update(
        self, id: int, patch_request: ResourcePoolUpdateRequest
    ) -> ResourcePool:
        resource = (
            ResourcePoolCreateOrUpdateResourceBuilder()
            .with_name(patch_request.name)
            .with_description(patch_request.description)
            .with_updated(utcnow())
            .build()
        )

        return await self.resource_pools_repository.update(id, resource)
