#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
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
        context: Context,
        resource_pools_repository: ResourcePoolRepository,
    ):
        super().__init__(context)
        self.resource_pools_repository = resource_pools_repository

    async def create(self, resource: CreateOrUpdateResource) -> ResourcePool:
        return await self.resource_pools_repository.create(resource)

    async def get_by_id(self, id: int) -> Optional[ResourcePool]:
        return await self.resource_pools_repository.get_by_id(id)

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[ResourcePool]:
        return await self.resource_pools_repository.list(
            token=token, size=size, query=query
        )

    async def update_by_id(
        self, id: int, resource: CreateOrUpdateResource
    ) -> ResourcePool:
        return await self.resource_pools_repository.update_by_id(id, resource)

    async def list_ids(self) -> set[int]:
        """Returns all the ids of the resource pools in the db."""
        return await self.resource_pools_repository.list_ids()
