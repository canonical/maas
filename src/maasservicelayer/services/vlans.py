# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.vlans import VlanBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.vlans import (
    VlansClauseFactory,
    VlansRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_FABRIC_VLAN_VIOLATION_TYPE,
)
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService

DEFAULT_VID = 0
DEFAULT_MTU = 1500


class VlansService(BaseService[Vlan, VlansRepository, VlanBuilder]):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        nodes_service: NodesService,
        vlans_repository: VlansRepository,
    ):
        super().__init__(context, vlans_repository)
        self.temporal_service = temporal_service
        self.nodes_service = nodes_service

    async def get_node_vlans(self, query: QuerySpec) -> List[Vlan]:
        return await self.repository.get_node_vlans(query=query)

    async def get_fabric_default_vlan(self, fabric_id: int) -> Vlan:
        return await self.repository.get_fabric_default_vlan(fabric_id)

    # When the VLAN is created it has no related IPRanges. For this reason it's not possible to enable DHCP
    # at creation time and we don't have to start the temporal workflow. For this reason, we don't have to override the create
    # method of the BaseService

    async def post_update_hook(
        self, old_resource: Vlan, updated_resource: Vlan
    ) -> None:
        # if the updated_resource has rack_ids, these will be found in the workflow, but removed ones will not
        system_ids = []
        if (
            old_resource.primary_rack_id
            and old_resource.primary_rack_id
            != updated_resource.primary_rack_id
        ):
            primary_rack = await self.nodes_service.get_by_id(
                old_resource.primary_rack_id
            )

            if primary_rack:
                system_ids.append(primary_rack.system_id)
        if (
            old_resource.secondary_rack_id
            and old_resource.secondary_rack_id
            != updated_resource.secondary_rack_id
        ):
            secondary_rack = await self.nodes_service.get_by_id(
                old_resource.secondary_rack_id
            )

            if secondary_rack:
                system_ids.append(secondary_rack.system_id)

        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                system_ids=system_ids, vlan_ids=[updated_resource.id]
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return

    async def post_update_many_hook(self, resources: List[Vlan]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def pre_delete_hook(self, resource_to_be_deleted: Vlan) -> None:
        default_fabric_vlan = await self.get_fabric_default_vlan(
            resource_to_be_deleted.fabric_id
        )
        if default_fabric_vlan == resource_to_be_deleted:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_FABRIC_VLAN_VIOLATION_TYPE,
                        message=f"The VLAN {resource_to_be_deleted.id} is the default VLAN for the fabric {resource_to_be_deleted.fabric_id} and can't be deleted.",
                    )
                ]
            )

    async def post_delete_hook(self, resource: Vlan) -> None:
        if resource.dhcp_on or resource.relay_vlan_id is not None:
            primary_rack = await self.nodes_service.get_by_id(
                resource.primary_rack_id  # type: ignore
            )
            system_ids = [primary_rack.system_id]  # type: ignore
            if resource.secondary_rack_id is not None:
                secondary_rack = await self.nodes_service.get_by_id(
                    resource.secondary_rack_id
                )
                assert secondary_rack is not None
                system_ids.append(secondary_rack.system_id)

            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(system_ids=system_ids),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )

    async def post_delete_many_hook(self, resources: List[Vlan]) -> None:
        # TODO: When implemented, adjust FabricsService.post_delete_hook
        #       and its associated unit tests.
        raise NotImplementedError("Not implemented yet.")

    async def reconfigure_all_active_dhcp(self):
        vlans = await self.repository.get_many(
            QuerySpec(where=VlansClauseFactory.with_dhcp_on(on=True))
        )
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(vlan_ids=[vlan.id for vlan in vlans]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
