#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address
from typing import List, Type

from sqlalchemy import and_, delete, func, join, select, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.operators import eq

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
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
from maasservicelayer.utils.date import utcnow


class StaticIPAddressClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.id, id))

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, type))

    @classmethod
    def with_node_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(
            condition=eq(StaticIPAddressTable.c.subnet_id, subnet_id)
        )

    @classmethod
    def with_subnet_id_in(cls, subnet_ids: list[int]) -> Clause:
        return Clause(
            condition=StaticIPAddressTable.c.subnet_id.in_(subnet_ids)
        )

    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address | None) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.ip, ip))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(StaticIPAddressTable.c.user_id, user_id))

    @classmethod
    def with_alloc_type(cls, alloc_type: IpAddressType) -> Clause:
        return Clause(
            condition=eq(StaticIPAddressTable.c.alloc_type, alloc_type)
        )

    @classmethod
    def with_interface_ids(cls, interface_ids: List[int]) -> Clause:
        return Clause(
            condition=InterfaceTable.c.id.in_(interface_ids),
            joins=[
                join(
                    StaticIPAddressTable,
                    InterfaceIPAddressTable,
                    eq(
                        StaticIPAddressTable.c.id,
                        InterfaceIPAddressTable.c.staticipaddress_id,
                    ),
                ),
                join(
                    InterfaceIPAddressTable,
                    InterfaceTable,
                    eq(
                        InterfaceIPAddressTable.c.interface_id,
                        InterfaceTable.c.id,
                    ),
                ),
            ],
        )


class StaticIPAddressRepository(BaseRepository):
    def get_repository_table(self) -> Table:
        return StaticIPAddressTable

    def get_model_factory(self) -> Type[StaticIPAddress]:
        return StaticIPAddress

    async def create_or_update(
        self, builder: StaticIPAddressBuilder
    ) -> StaticIPAddress:
        now = utcnow()
        builder.created = now
        builder.updated = now
        resource = self.mapper.build_resource(builder)
        stmt = insert(StaticIPAddressTable).values(**resource.get_values())
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[
                StaticIPAddressTable.c.ip,
                StaticIPAddressTable.c.alloc_type,
            ],
            set_=resource.get_values(),
        ).returning(StaticIPAddressTable)

        result = (await self.execute_stmt(upsert_stmt)).one()
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
                        family,
                    ),
                    InterfaceTable.c.id.in_(
                        [interface.id for interface in interfaces]
                    ),
                    eq(
                        StaticIPAddressTable.c.alloc_type,
                        IpAddressType.DISCOVERED,
                    ),
                ),
            )
        )

        result = (
            await self.execute_stmt(
                stmt,
            )
        ).all()

        return [StaticIPAddress(**row._asdict()) for row in result]

    async def get_for_interfaces(
        self, interface_ids: list[int]
    ) -> list[StaticIPAddress]:
        stmt = (
            select(StaticIPAddressTable)
            .select_from(InterfaceIPAddressTable)
            .join(
                StaticIPAddressTable,
                StaticIPAddressTable.c.id
                == InterfaceIPAddressTable.c.staticipaddress_id,
            )
            .filter(InterfaceIPAddressTable.c.interface_id.in_(interface_ids))
        )

        result = (await self.execute_stmt(stmt)).all()

        return [StaticIPAddress(**row._asdict()) for row in result]

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
        )
        stmt = query.enrich_stmt(stmt)
        results = (await self.execute_stmt(stmt)).all()
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
        results = (await self.execute_stmt(stmt)).all()
        return [MacAddress(row._asdict()["mac_address"]) for row in results]

    async def unlink_from_interfaces(self, staticipaddress_id: int):
        stmt = delete(InterfaceIPAddressTable).where(
            eq(
                InterfaceIPAddressTable.c.staticipaddress_id,
                staticipaddress_id,
            )
        )
        await self.execute_stmt(stmt)
