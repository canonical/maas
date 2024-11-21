#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service
from maasservicelayer.services.temporal import TemporalService


class IPRangesService(Service):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        ipranges_repository: Optional[IPRangesRepository] = None,
    ):
        super().__init__(context)
        self.temporal_service = temporal_service
        self.ipranges_repository = (
            ipranges_repository
            if ipranges_repository
            else IPRangesRepository(context)
        )

    async def get_dynamic_range_for_ip(
        self, subnet: Subnet, ip: IPvAnyAddress
    ) -> IPRange | None:
        return await self.ipranges_repository.get_dynamic_range_for_ip(
            subnet, ip
        )

    async def create(self, resource: CreateOrUpdateResource) -> IPRange:
        iprange = await self.ipranges_repository.create(resource)
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return iprange

    async def update_by_id(
        self, id: int, resource: CreateOrUpdateResource
    ) -> IPRange | None:
        iprange = await self.ipranges_repository.update_by_id(id, resource)
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(ip_range_ids=[iprange.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return iprange

    async def delete_by_id(self, id: int) -> None:
        iprange = await self.ipranges_repository.get_by_id(id=id)
        await self.ipranges_repository.delete_by_id(id)
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(subnet_ids=[iprange.subnet_id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
