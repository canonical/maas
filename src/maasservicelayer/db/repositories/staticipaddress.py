import datetime
from typing import List, Optional

from netaddr import IPAddress
from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.sql.operators import eq

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
    QuerySpec,
)
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    StaticIPAddressTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet

STATICIPADDRESS_FIELDS = [
    StaticIPAddressTable.c.id,
    StaticIPAddressTable.c.ip,
    StaticIPAddressTable.c.alloc_type,
    StaticIPAddressTable.c.lease_time,
    StaticIPAddressTable.c.temp_expires_on,
    StaticIPAddressTable.c.subnet_id,
    StaticIPAddressTable.c.created,
    StaticIPAddressTable.c.updated,
]


class StaticIPAddressResourceBuilder(CreateOrUpdateResourceBuilder):
    def with_ip(self, ip: str | None) -> "StaticIPAddressResourceBuilder":
        self._request.set_value(StaticIPAddressTable.c.ip.name, ip)
        return self

    def with_alloc_type(
        self, alloc_type: IpAddressType
    ) -> "StaticIPAddressResourceBuilder":
        self._request.set_value(
            StaticIPAddressTable.c.alloc_type.name, alloc_type.value
        )
        return self

    def with_lease_time(
        self, lease_time: int
    ) -> "StaticIPAddressResourceBuilder":
        self._request.set_value(
            StaticIPAddressTable.c.lease_time.name, lease_time
        )
        return self

    def with_temp_expires_on(
        self, temp_expires_on: datetime.datetime
    ) -> "StaticIPAddressResourceBuilder":
        self._request.set_value(
            StaticIPAddressTable.c.temp_expires_on.name, temp_expires_on
        )
        return self

    def with_subnet_id(
        self, subnet_id: int
    ) -> "StaticIPAddressResourceBuilder":
        self._request.set_value(
            StaticIPAddressTable.c.subnet_id.name, subnet_id
        )
        return self


class StaticIPAddressRepository(BaseRepository):
    async def find_by_id(self, id: int) -> StaticIPAddress | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[StaticIPAddress]:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        stmt = delete(StaticIPAddressTable).where(
            StaticIPAddressTable.c.id == id
        )
        await self.connection.execute(stmt)

    async def create(
        self, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        stmt = (
            insert(StaticIPAddressTable)
            .returning(*STATICIPADDRESS_FIELDS)
            .values(**resource.get_values())
        )

        result = (await self.connection.execute(stmt)).one()
        return StaticIPAddress(**result._asdict())

    async def update(
        self, id: int | None, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        stmt = None

        if id:
            stmt = (
                update(StaticIPAddressTable)
                .where(StaticIPAddressTable.c.id == id)
                .returning(*STATICIPADDRESS_FIELDS)
                .values(**resource.get_values())
            )
        else:
            stmt = (
                update(StaticIPAddressTable)
                .where(
                    StaticIPAddressTable.c.ip
                    == IPAddress(resource.get_values()["ip"]),
                    StaticIPAddressTable.c.alloc_type
                    == resource.get_values()["alloc_type"],
                    StaticIPAddressTable.c.subnet_id
                    == resource.get_values()["subnet_id"],
                )
                .returning(*STATICIPADDRESS_FIELDS)
                .values(**resource.get_values())
            )

        result = (await self.connection.execute(stmt)).one()
        return StaticIPAddress(**result._asdict())

    async def get_discovered_ips_in_family_for_interfaces(
        self,
        interfaces: List[Interface],
        family: IpAddressFamily = IpAddressFamily.IPV4,
    ) -> List[StaticIPAddress]:
        stmt = (
            select(StaticIPAddressTable)
            .select_from(StaticIPAddressTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                InterfaceTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .where(
                and_(
                    eq(
                        func.family(StaticIPAddressTable.c.ip),
                        IpAddressFamily.IPV4.value,
                    ),
                    InterfaceTable.c.id.in_(
                        [interface.id for interface in interfaces]
                    ),
                ),
            )
        )

        result = (
            await self.connection.execute(
                stmt,
            )
        ).all()

        return [StaticIPAddress(**row._asdict()) for row in result]

    async def get_for_interfaces(
        self,
        interfaces: List[Interface],
        subnet: Optional[Subnet] = None,
        ip: Optional[StaticIPAddress] = None,
        alloc_type: Optional[IpAddressType] = None,
    ) -> StaticIPAddress | None:
        stmt = (
            select(StaticIPAddressTable)
            .select_from(InterfaceTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.interface_id == InterfaceTable.c.id,
            )
            .join(
                StaticIPAddressTable,
                StaticIPAddressTable.c.id
                == InterfaceIPAddressTable.c.staticipaddress_id,
            )
            .filter(
                InterfaceTable.c.id.in_([iface.id for iface in interfaces]),
            )
        )

        if subnet:
            stmt = stmt.filter(StaticIPAddressTable.c.subnet_id == subnet.id)

        if ip:
            stmt = stmt.filter(StaticIPAddressTable.c.ip == ip.ip)

        if alloc_type:
            stmt = stmt.filter(
                StaticIPAddressTable.c.alloc_type == alloc_type.value
            )

        result = (await self.connection.execute(stmt)).first()

        if result:
            return StaticIPAddress(**result._asdict())
        return None
