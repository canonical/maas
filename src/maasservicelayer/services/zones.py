#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from dataclasses import dataclass
from typing import List

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.zones import ZonesRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
)
from maasservicelayer.models.zones import Zone, ZoneBuilder
from maasservicelayer.services._base import BaseService, Service, ServiceCache
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.vmcluster import VmClustersService


@dataclass(slots=True)
class ZonesServiceCache(ServiceCache):
    default_zone: Zone | None = None


class ZonesService(BaseService[Zone, ZonesRepository, ZoneBuilder]):
    def __init__(
        self,
        context: Context,
        nodes_service: NodesService,
        vmcluster_service: VmClustersService,
        zones_repository: ZonesRepository,
        cache: ZonesServiceCache | None = None,
    ):
        super().__init__(context, zones_repository, cache)
        self.nodes_service = nodes_service
        self.vmcluster_service = vmcluster_service

    @staticmethod
    def build_cache_object() -> ZonesServiceCache:
        return ZonesServiceCache()

    @Service.from_cache_or_execute(attr="default_zone")
    async def get_default_zone(self) -> Zone:
        return await self.repository.get_default_zone()

    async def post_delete_many_hook(self, resources: List[Zone]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def pre_delete_hook(self, resource_to_be_deleted: Zone) -> None:
        default_zone = await self.get_default_zone()
        if default_zone.id == resource_to_be_deleted.id:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
                        message="The default zone can not be deleted.",
                    )
                ]
            )

    async def post_delete_hook(self, resource: Zone) -> None:
        default_zone = await self.get_default_zone()
        # Cascade deletion to the related models and move the resources from the deleted zone to the default zone
        await self.nodes_service.move_to_zone(resource.id, default_zone.id)
        await self.nodes_service.move_bmcs_to_zone(
            resource.id, default_zone.id
        )
        await self.vmcluster_service.move_to_zone(resource.id, default_zone.id)
