# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.vlans import VlansRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services._base import Service
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService


class VlansService(Service):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        nodes_service: NodesService,
        vlans_repository: VlansRepository | None = None,
    ):
        super().__init__(context)
        self.temporal_service = temporal_service
        self.nodes_service = nodes_service
        self.vlans_repository = (
            vlans_repository if vlans_repository else VlansRepository(context)
        )

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Vlan]:
        return await self.vlans_repository.list(
            token=token,
            size=size,
            query=query,
        )

    async def get_by_id(self, fabric_id: int, vlan_id: int) -> Vlan | None:
        vlan = await self.vlans_repository.find_by_id(id=vlan_id)
        if vlan is None or vlan.fabric_id != fabric_id:
            return None
        return vlan

    async def get_node_vlans(self, query: QuerySpec) -> List[Vlan]:
        return await self.vlans_repository.get_node_vlans(query=query)

    async def create(self, resource: CreateOrUpdateResource) -> Vlan:
        vlan = await self.vlans_repository.create(resource)
        if vlan.dhcp_on or vlan.relay_vlan:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(vlan_ids=[vlan.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return vlan

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Vlan | None:
        vlan = await self.vlans_repository.update(id, resource)

        # dhcp_on could've been true prior to update or updated to true,
        # so always register configure-dhcp on update
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(vlan_ids=[vlan.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return vlan

    async def delete(self, id: int) -> None:
        vlan = await self.vlans_repository.find_by_id(id=id)
        await self.vlans_repository.delete(id)
        if vlan.dhcp_on or vlan.relay_vlan:
            primary_rack = await self.nodes_service.get_by_id(
                vlan.primary_rack_id
            )
            system_ids = [primary_rack.system_id]
            if vlan.secondary_rack_id:
                secondary_rack = await self.nodes_service.get_by_id(
                    vlan.second_rack_id
                )
                system_ids.append(secondary_rack.system_id)

            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(system_ids=system_ids),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
