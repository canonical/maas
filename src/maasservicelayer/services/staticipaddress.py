#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List, Optional

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.models.base import Unset
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.temporal import TemporalService


class StaticIPAddressService(
    BaseService[
        StaticIPAddress, StaticIPAddressRepository, StaticIPAddressBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        staticipaddress_repository: StaticIPAddressRepository,
    ):
        super().__init__(context, staticipaddress_repository)
        self.temporal_service = temporal_service

    async def post_create_hook(self, resource: StaticIPAddress) -> None:
        if resource.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[resource.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return

    async def post_update_hook(
        self, old_resource: StaticIPAddress, updated_resource: StaticIPAddress
    ) -> None:
        if updated_resource.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[updated_resource.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return

    async def post_update_many_hook(
        self, resources: List[StaticIPAddress]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def create_or_update(
        self, builder: StaticIPAddressBuilder
    ) -> StaticIPAddress:
        ip = await self.repository.create_or_update(builder)
        if ip.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return ip

    async def post_delete_hook(self, resource: StaticIPAddress) -> None:
        if resource.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(
                    subnet_ids=[resource.subnet_id]
                ),  # use parent id on delete
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )

    async def post_delete_many_hook(
        self, resources: List[StaticIPAddress]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def get_discovered_ips_in_family_for_interfaces(
        self,
        interfaces: list[Interface],
        family: IpAddressFamily = IpAddressFamily.IPV4,
    ) -> List[StaticIPAddress]:
        return (
            await self.repository.get_discovered_ips_in_family_for_interfaces(
                interfaces, family=family
            )
        )

    async def get_for_interfaces(
        self,
        interfaces: list[Interface],
        subnet: Optional[Subnet] = None,
        ip: Optional[StaticIPAddress] = None,
        alloc_type: Optional[int] = None,
    ) -> StaticIPAddress | None:
        return await self.repository.get_for_interfaces(
            interfaces, subnet=subnet, ip=ip, alloc_type=alloc_type
        )

    async def get_for_nodes(self, query: QuerySpec) -> list[StaticIPAddress]:
        return await self.repository.get_for_nodes(query=query)

    async def get_mac_addresses(self, query: QuerySpec) -> list[MacAddress]:
        return await self.repository.get_mac_addresses(query=query)

    async def update_many(
        self, query: QuerySpec, builder: StaticIPAddressBuilder
    ) -> List[StaticIPAddress]:
        updated_resources = await self.repository.update_many(
            query=query, builder=builder
        )

        if self._must_trigger_update_hook(builder):
            await self.post_update_many_hook(updated_resources)
        return updated_resources

    async def _must_trigger_update_hook(
        self, builder: StaticIPAddressBuilder
    ) -> bool:
        # TODO: change this when refactoring builders and update_many
        if (
            not isinstance(builder.ip, Unset)
            or not isinstance(builder.alloc_type, Unset)
            or not isinstance(builder.subnet_id, Unset)
        ):
            return True
        return False
