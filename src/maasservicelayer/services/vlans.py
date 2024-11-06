# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from typing import List

from sqlalchemy.ext.asyncio import AsyncConnection

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
        connection: AsyncConnection,
        temporal_service: TemporalService,
        nodes_service: NodesService,
        vlans_repository: VlansRepository | None = None,
    ):
        super().__init__(connection)
        self.temporal_service = temporal_service
        self.nodes_service = nodes_service
        self.vlans_repository = (
            vlans_repository
            if vlans_repository
            else VlansRepository(connection)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Vlan]:
        return await self.vlans_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Vlan | None:
        return await self.vlans_repository.find_by_id(id=id)

    async def get_node_vlans(self, query: QuerySpec) -> List[Vlan]:
        return await self.vlans_repository.get_node_vlans(query=query)

    async def create(self, resource: CreateOrUpdateResource) -> Vlan:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

        vlan = await self.vlans_repository.create(resource)
        if vlan.dhcp_on or vlan.relay_vlan:
            self.temporal_service.register_or_update_workflow_call(
                "configure-dhcp",
                ConfigureDHCPParam(vlan_ids=[vlan.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return vlan

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Vlan | None:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

        vlan = await self.vlans_repository.update(id, resource)

        # dhcp_on could've been true prior to update or updated to true,
        # so always register configure-dhcp on update
        self.temporal_service.register_or_update_workflow_call(
            "configure-dhcp",
            ConfigureDHCPParam(vlan_ids=[vlan.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return vlan

    async def delete(self, id: int) -> None:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

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
            "configure-dhcp",
            ConfigureDHCPParam(system_ids=system_ids),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
