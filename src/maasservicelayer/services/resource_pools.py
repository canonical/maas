#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.resource_pools import ResourcePoolBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolRepository,
)
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services.base import BaseService


class ResourcePoolsService(
    BaseService[ResourcePool, ResourcePoolRepository, ResourcePoolBuilder]
):
    def __init__(
        self,
        context: Context,
        resource_pools_repository: ResourcePoolRepository,
    ):
        super().__init__(context, resource_pools_repository)

    async def list_ids(self) -> set[int]:
        """Returns all the ids of the resource pools in the db."""
        return await self.repository.list_ids()
