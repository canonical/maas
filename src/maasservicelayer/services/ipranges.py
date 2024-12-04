#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import List

from pydantic import IPvAnyAddress

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsClauseFactory,
)
from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.dhcpsnippets import DhcpSnippetsService
from maasservicelayer.services.temporal import TemporalService


class IPRangesService(BaseService[IPRange, IPRangesRepository]):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        dhcpsnippets_service: DhcpSnippetsService,
        ipranges_repository: IPRangesRepository,
    ):
        super().__init__(context, ipranges_repository)
        self.temporal_service = temporal_service
        self.dhcpsnippets_service = dhcpsnippets_service
        self.ipranges_repository = ipranges_repository

    async def get_dynamic_range_for_ip(
        self, subnet: Subnet, ip: IPvAnyAddress
    ) -> IPRange | None:
        return await self.repository.get_dynamic_range_for_ip(subnet, ip)

    async def post_create_hook(self, resource: IPRange) -> None:
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(ip_range_ids=[resource.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return

    async def post_update_hook(
        self, old_resource: IPRange, updated_resource: IPRange
    ) -> None:
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(ip_range_ids=[updated_resource.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return

    async def post_update_many_hook(self, resources: List[IPRange]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def post_delete_hook(self, resource: IPRange) -> None:
        await self.dhcpsnippets_service.delete_many(
            query=QuerySpec(
                where=DhcpSnippetsClauseFactory.with_iprange_id(resource.id)
            )
        )
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(subnet_ids=[resource.subnet_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def post_delete_many_hook(self, resources: List[IPRange]) -> None:
        raise NotImplementedError("Not implemented yet.")
