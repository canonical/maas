from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressFamily
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service


class StaticIPAddressService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        staticipaddress_repository: Optional[StaticIPAddressRepository] = None,
    ):
        super().__init__(connection)
        self.staticipaddress_repository = (
            staticipaddress_repository
            if staticipaddress_repository
            else StaticIPAddressRepository(connection)
        )

    async def create(
        self, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        return await self.staticipaddress_repository.create(resource)

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        return await self.staticipaddress_repository.update(id, resource)

    async def create_or_update(
        self, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        return await self.staticipaddress_repository.create_or_update(resource)

    async def delete(self, id: int) -> None:
        await self.staticipaddress_repository.delete(id)

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
