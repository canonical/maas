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
        vlan = await self.vlans_repository.get_by_id(id=vlan_id)
        if vlan is None or vlan.fabric_id != fabric_id:
            return None
        return vlan

    async def get_node_vlans(self, query: QuerySpec) -> List[Vlan]:
        return await self.vlans_repository.get_node_vlans(query=query)

    async def create(self, resource: CreateOrUpdateResource) -> Vlan:
        # When the VLAN is created it has no related IPRanges. For this reason it's not possible to enable DHCP
        # at creation time and we don't have to start the temporal workflow.
        return await self.vlans_repository.create(resource)

    async def update_by_id(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Vlan | None:
        vlan = await self.vlans_repository.update_by_id(id, resource)

        # dhcp_on could've been true prior to update or updated to true,
        # so always register configure-dhcp on update
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(vlan_ids=[vlan.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return vlan

    async def delete_by_id(self, id: int, etag_if_match: str | None = None):
        vlan = await self.vlans_repository.get_by_id(id=id)
        return await self._delete(vlan, etag_if_match)

    async def delete(self, query: QuerySpec, etag_if_match: str | None = None):
        vlan = await self.vlans_repository.get_one(query=query)
        return await self._delete(vlan, etag_if_match)

    async def _delete(
        self, vlan: Vlan | None, etag_if_match: str | None = None
    ) -> None:
        if not vlan:
            return None

        self.etag_check(vlan, etag_if_match)
        await self.vlans_repository.delete_by_id(vlan.id)

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
