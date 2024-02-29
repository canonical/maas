from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BadRequestException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasapiserver.common.services._base import Service
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.zones import ZoneRequest
from maasapiserver.v3.db.zones import ZonesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.zones import Zone
from maasapiserver.v3.services.bmc import BmcService
from maasapiserver.v3.services.nodes import NodesService
from maasapiserver.v3.services.vmcluster import VmClustersService


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

    async def create(self, zone_request: ZoneRequest) -> Zone:
        return await self.zones_repository.create(zone_request)

    async def get_by_id(self, id: int) -> Optional[Zone]:
        return await self.zones_repository.find_by_id(id)

    async def get_by_name(self, name: str) -> Optional[Zone]:
        return await self.zones_repository.find_by_name(name)

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[Zone]:
        return await self.zones_repository.list(pagination_params)

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
