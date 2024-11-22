#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.zones import ZonesRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.zones import Zone
from maasservicelayer.services._base import Service
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.vmcluster import VmClustersService


class ZonesService(Service):
    def __init__(
        self,
        context: Context,
        nodes_service: NodesService,
        vmcluster_service: VmClustersService,
        zones_repository: ZonesRepository,
    ):
        super().__init__(context)
        self.nodes_service = nodes_service
        self.zones_repository = zones_repository
        self.vmcluster_service = vmcluster_service

    async def create(self, resource: CreateOrUpdateResource) -> Zone:
        return await self.zones_repository.create(resource)

    async def get_by_id(self, id: int) -> Optional[Zone]:
        return await self.zones_repository.get_by_id(id)

    async def list(
        self, token: str | None, size: int, query: QuerySpec
    ) -> ListResult[Zone]:
        return await self.zones_repository.list(
            token=token, size=size, query=query
        )

    async def update_by_id(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Zone:
        return await self.zones_repository.update_by_id(id, resource)

    async def delete_by_id(
        self, zone_id: int, etag_if_match: str | None = None
    ) -> None:
        """
        Delete a zone. All the resources in the zone will be moved to the default zone.
        """
        zone = await self.get_by_id(zone_id)
        if not zone:
            return None

        self.etag_check(zone, etag_if_match)
        default_zone = await self.zones_repository.get_default_zone()

        if default_zone.id == zone.id:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
                        message="The default zone can not be deleted.",
                    )
                ]
            )
        await self.zones_repository.delete_by_id(zone_id)

        # Cascade deletion to the related models and move the resources from the deleted zone to the default zone
        await self.nodes_service.move_to_zone(zone_id, default_zone.id)
        await self.nodes_service.move_bmcs_to_zone(zone_id, default_zone.id)
        await self.vmcluster_service.move_to_zone(zone_id, default_zone.id)
