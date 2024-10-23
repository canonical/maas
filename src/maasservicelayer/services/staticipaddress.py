from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
    StaticIPAddressResourceBuilder,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
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

    async def create_or_update(
        self,
        ip: str | None,
        lease_time: int | None,
        alloc_type: IpAddressType,
        subnet_id: int | None,
        created: datetime | None,
        updated: datetime,
        temp_expires_on: datetime | None = None,
    ) -> StaticIPAddress:
        resource = self._build_resource(
            ip=ip,
            lease_time=lease_time,
            alloc_type=alloc_type,
            temp_expires_on=temp_expires_on,
            subnet_id=subnet_id,
            created=created,
            updated=updated,
        )
        if created:
            try:
                ip = await self.staticipaddress_repository.create(resource)
            except AlreadyExistsException:
                ip = await self.staticipaddress_repository.update(
                    None, resource
                )
        else:
            ip = await self.staticipaddress_repository.update(None, resource)
        return ip

    async def get_discovered_ips_in_family_for_interfaces(
        self,
        interfaces: list[Interface],
        family: IpAddressFamily = IpAddressFamily.IPV4,
    ):
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

    async def create(
        self,
        ip: str | None,
        lease_time: int | None,
        alloc_type: IpAddressType,
        subnet_id: int | None,
        created: datetime,
        updated: datetime,
        temp_expires_on: datetime | None = None,
    ) -> StaticIPAddress:

        resource = self._build_resource(
            ip=ip,
            lease_time=lease_time,
            alloc_type=alloc_type,
            temp_expires_on=temp_expires_on,
            subnet_id=subnet_id,
            created=created,
            updated=updated,
        )
        return await self.staticipaddress_repository.create(resource)

    async def update(
        self,
        id: int,
        ip: str | None,
        lease_time: int | None,
        alloc_type: IpAddressType,
        subnet_id: int,
        created: datetime | None,
        updated: datetime,
        temp_expires_on: datetime | None = None,
    ) -> StaticIPAddress:
        resource = self._build_resource(
            ip=ip,
            lease_time=lease_time,
            alloc_type=alloc_type,
            temp_expires_on=temp_expires_on,
            subnet_id=subnet_id,
            created=created,
            updated=updated,
        )
        return await self.staticipaddress_repository.update(id, resource)

    async def delete(self, id: int) -> None:
        await self.staticipaddress_repository.delete(id)

    def _build_resource(
        self,
        ip: str | None,
        lease_time: int | None,
        alloc_type: IpAddressType,
        subnet_id: int | None,
        temp_expires_on: datetime | None,
        created: datetime | None,
        updated: datetime,
    ) -> CreateOrUpdateResource:
        resource = (
            StaticIPAddressResourceBuilder()
            .with_ip(ip)
            .with_alloc_type(alloc_type)
            .with_updated(updated)
        )
        if lease_time:
            resource = resource.with_lease_time(lease_time)

        if subnet_id:
            resource = resource.with_subnet_id(subnet_id)

        if temp_expires_on:
            resource = resource.with_temp_expires_on(temp_expires_on)

        if created:
            resource = resource.with_created(created)

        return resource.build()
