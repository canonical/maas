# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.fabrics import FabricsRepository
from maasservicelayer.db.repositories.vlans import VlanResourceBuilder
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services._base import Service
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow


class FabricsService(Service):
    def __init__(
        self,
        context: Context,
        vlans_service: VlansService,
        fabrics_repository: FabricsRepository,
    ):
        super().__init__(context)
        self.vlans_service = vlans_service
        self.fabrics_repository = fabrics_repository

    async def create(self, resource: CreateOrUpdateResource) -> Fabric:
        new_fabric = await self.fabrics_repository.create(resource)

        # Create default VLAN for new Fabric
        now = utcnow()
        new_vlan_resource = (
            VlanResourceBuilder()
            .with_vid()
            .with_name("Default VLAN")
            .with_fabric_id(new_fabric.id)
            .with_mtu()
            .with_dhcp_on(False)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        await self.vlans_service.create(resource=new_vlan_resource)

        return new_fabric

    async def list(self, token: str | None, size: int) -> ListResult[Fabric]:
        return await self.fabrics_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Fabric | None:
        return await self.fabrics_repository.get_by_id(id=id)
