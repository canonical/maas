from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasapiserver.common.services._base import Service
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolPatchRequest,
    ResourcePoolRequest,
)
from maasapiserver.v3.db.resource_pools import ResourcePoolRepository
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
        return await self.resource_pools_repository.create(
            resource_pool_request
        )

    async def get_by_id(self, id: int) -> Optional[ResourcePool]:
        return await self.resource_pools_repository.find_by_id(id)

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[ResourcePool]:
        return await self.resource_pools_repository.list(pagination_params)

    async def patch(
        self, id: int, patch_request: ResourcePoolPatchRequest
    ) -> ResourcePool:
        resource_pool = await self.get_by_id(id)
        if not resource_pool:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Resource pool with id '{id}' does not exist.",
                    )
                ]
            )
        resource_pool = resource_pool.copy(
            update=patch_request.dict(exclude_none=True)
        )
        return await self.resource_pools_repository.update(resource_pool)
