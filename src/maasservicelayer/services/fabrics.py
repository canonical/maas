# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.fabrics import FabricsRepository
from maasservicelayer.db.repositories.vlans import VlanResourceBuilder
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow


class FabricsService(BaseService[Fabric, FabricsRepository]):
    def __init__(
        self,
        context: Context,
        vlans_service: VlansService,
        fabrics_repository: FabricsRepository,
    ):
        super().__init__(context, fabrics_repository)
        self.vlans_service = vlans_service

    async def post_create_hook(self, resource: Fabric) -> None:
        # Create default VLAN for new Fabric
        now = utcnow()
        new_vlan_resource = (
            VlanResourceBuilder()
            .with_vid()
            .with_name("Default VLAN")
            .with_description()
            .with_fabric_id(resource.id)
            .with_mtu()
            .with_dhcp_on(False)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        await self.vlans_service.create(resource=new_vlan_resource)

        return
