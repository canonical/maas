#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services._base import Service


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

    async def create(self, resource: CreateOrUpdateResource) -> ResourcePool:
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
        self, id: int, resource: CreateOrUpdateResource
    ) -> ResourcePool:
        return await self.resource_pools_repository.update(id, resource)
