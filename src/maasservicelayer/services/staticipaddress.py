from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service
from maasservicelayer.services.temporal import TemporalService


class StaticIPAddressService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        temporal_service: TemporalService,
        staticipaddress_repository: Optional[StaticIPAddressRepository] = None,
    ):
        super().__init__(connection)
        self.temporal_service = temporal_service
        self.staticipaddress_repository = (
            staticipaddress_repository
            if staticipaddress_repository
            else StaticIPAddressRepository(connection)
        )

    async def create(
        self, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

        ip = await self.staticipaddress_repository.create(resource)
        if ip.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                "configure-dhcp",
                ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return ip

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

        ip = await self.staticipaddress_repository.update(id, resource)
        if ip.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                "configure-dhcp",
                ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return ip

    async def create_or_update(
        self, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

        ip = await self.staticipaddress_repository.create_or_update(resource)
        if ip.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                "configure-dhcp",
                ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return ip

    async def delete(self, id: int) -> None:
        # avoiding circular import of ServiceCollectionV3
        from maastemporalworker.workflow.dhcp import (
            ConfigureDHCPParam,
            merge_configure_dhcp_param,
        )

        ip = await self.staticipaddress_repository.find_by_id(id=id)
        await self.staticipaddress_repository.delete(id)

        if ip.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                "configure-dhcp",
                ConfigureDHCPParam(
                    subnet_ids=[ip.subnet_id]
                ),  # use parent id on delete
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )

    async def get_discovered_ips_in_family_for_interfaces(
        self,
        interfaces: list[Interface],
        family: IpAddressFamily = IpAddressFamily.IPV4,
    ) -> List[StaticIPAddress]:
        return await self.staticipaddress_repository.get_discovered_ips_in_family_for_interfaces(
            interfaces, family=family
        )

    async def get_for_interfaces(
        self,
        interfaces: list[Interface],
        subnet: Optional[Subnet] = None,
        ip: Optional[StaticIPAddress] = None,
        alloc_type: Optional[int] = None,
    ) -> StaticIPAddress | None:
        return await self.staticipaddress_repository.get_for_interfaces(
            interfaces, subnet=subnet, ip=ip, alloc_type=alloc_type
        )
