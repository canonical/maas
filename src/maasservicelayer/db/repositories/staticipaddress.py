import datetime
from typing import List, Optional, Type

from pydantic import IPvAnyAddress
from sqlalchemy import and_, func, select, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.operators import eq

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    ResourceBuilder,
)
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    SubnetTable,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet


class StaticIPAddressResourceBuilder(ResourceBuilder):
    def with_ip(
        self, ip: IPvAnyAddress | None
    ) -> "StaticIPAddressResourceBuilder":
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


class StaticIPAddressClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.id, id))

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, type))

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(
            condition=eq(StaticIPAddressTable.c.subnet_id, subnet_id)
        )

    @classmethod
    def with_ip(cls, ip: IPvAnyAddress) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.ip, ip))


class StaticIPAddressRepository(BaseRepository):
    def get_repository_table(self) -> Table:
        return StaticIPAddressTable

    def get_model_factory(self) -> Type[StaticIPAddress]:
        return StaticIPAddress

    async def create_or_update(
        self, resource: CreateOrUpdateResource
    ) -> StaticIPAddress:
        stmt = insert(StaticIPAddressTable).values(**resource.get_values())
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[
                StaticIPAddressTable.c.ip,
                StaticIPAddressTable.c.alloc_type,
            ],
            set_=resource.get_values(),
        ).returning(StaticIPAddressTable)

        result = (await self.connection.execute(upsert_stmt)).one()
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

    async def get_for_nodes(self, query: QuerySpec) -> list[StaticIPAddress]:
        stmt = (
            select(
                StaticIPAddressTable,
            )
            .select_from(NodeTable)
            .join(
                NodeConfigTable,
                NodeTable.c.current_config_id == NodeConfigTable.c.id,
            )
            .join(
                InterfaceTable,
                NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
            )
            .join(
                InterfaceIPAddressTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .join(
                StaticIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                SubnetTable,
                SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
            )
            .where(query.where.condition)
        )
        results = (await self.connection.execute(stmt)).all()
        return [StaticIPAddress(**row._asdict()) for row in results]

    async def get_mac_addresses(self, query: QuerySpec) -> list[MacAddress]:
        stmt = (
            select(InterfaceTable.c.mac_address)
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
        )
        stmt = query.enrich_stmt(stmt)
        results = (await self.connection.execute(stmt)).all()
        return [MacAddress(row._asdict()["mac_address"]) for row in results]
