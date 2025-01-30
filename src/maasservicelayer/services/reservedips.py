# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from pydantic import IPvAnyAddress

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.reservedips import ReservedIPBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.reservedips import ReservedIPsRepository
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.temporal import TemporalService


class ReservedIPsService(
    BaseService[ReservedIP, ReservedIPsRepository, ReservedIPBuilder]
):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        reservedips_repository: ReservedIPsRepository,
    ):
        super().__init__(context, reservedips_repository)
        self.temporal_service = temporal_service

    async def post_create_hook(self, resource: ReservedIP) -> None:
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(reserved_ip_ids=[resource.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return

    async def post_delete_hook(self, resource: ReservedIP) -> None:
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(reserved_ip_ids=[resource.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return

    async def post_delete_many_hook(self, resources: List[ReservedIP]) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def exists_within_subnet_iprange(
        self, subnet_id: int, start_ip: IPvAnyAddress, end_ip: IPvAnyAddress
    ) -> bool:
        return await self.repository.exists_within_subnet_ip_range(
            subnet_id=subnet_id, start_ip=start_ip, end_ip=end_ip
        )
