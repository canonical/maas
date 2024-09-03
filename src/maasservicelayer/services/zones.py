#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.filters import FilterQuery
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.zones import ZonesRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.zones import Zone
from maasservicelayer.services._base import Service
from maasservicelayer.services.bmc import BmcService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.vmcluster import VmClustersService


class ZonesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        zones_repository: ZonesRepository | None = None,
        nodes_service: NodesService | None = None,
        bmc_service: BmcService | None = None,
        vmcluster_service: VmClustersService | None = None,
    ):
        super().__init__(connection)
        self.zones_repository = (
            zones_repository
            if zones_repository
            else ZonesRepository(connection)
        )
        self.nodes_service = (
            nodes_service if nodes_service else NodesService(connection)
        )
        self.bmc_service = (
            bmc_service if bmc_service else BmcService(connection)
        )
        self.vmcluster_service = (
            vmcluster_service
            if vmcluster_service
            else VmClustersService(connection)
        )

    async def create(self, resource: CreateOrUpdateResource) -> Zone:
        return await self.zones_repository.create(resource)

    async def get_by_id(self, id: int) -> Optional[Zone]:
        return await self.zones_repository.find_by_id(id)

    async def get_by_name(self, name: str) -> Optional[Zone]:
        return await self.zones_repository.find_by_name(name)

    async def list(
        self, token: str | None, size: int, query: FilterQuery
    ) -> ListResult[Zone]:
        return await self.zones_repository.list(
            token=token, size=size, query=query
        )

    async def delete(
        self, zone_id: int, etag_if_match: str | None = None
    ) -> None:
        """
        Delete a zone. All the resources in the zone will be moved to the default zone.
        """
        zone = await self.get_by_id(zone_id)
        if not zone:
            return None
        if etag_if_match is not None and zone.etag() != etag_if_match:
            raise PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message=f"The resource etag '{zone.etag()}' did not match '{etag_if_match}'.",
                    )
                ]
            )
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
        await self.zones_repository.delete(zone_id)

        # Cascade deletion to the related models and move the resources from the deleted zone to the default zone
        await self.nodes_service.move_to_zone(zone_id, default_zone.id)
        await self.bmc_service.move_to_zone(zone_id, default_zone.id)
        await self.vmcluster_service.move_to_zone(zone_id, default_zone.id)
