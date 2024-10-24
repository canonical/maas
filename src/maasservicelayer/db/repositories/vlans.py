#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from sqlalchemy import desc, select
from sqlalchemy.sql.operators import eq, le, or_

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    SubnetTable,
    VlanTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vlans import Vlan


class VlansClauseFactory(ClauseFactory):
    @classmethod
    def with_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, type))


class VlansRepository(BaseRepository[Vlan]):
    async def create(self, resource: CreateOrUpdateResource) -> Vlan:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Vlan | None:
        stmt = select("*").filter(eq(VlanTable.c.id, id))

        result = await self.connection.execute(stmt)
        vlan = result.first()
        if not vlan:
            return None
        return Vlan(**vlan._asdict())

    async def find_by_name(self, name: str) -> Vlan | None:
        raise NotImplementedError()

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Vlan]:
        # TODO: use the query for the filters
        stmt = (
            select("*")
            .select_from(VlanTable)
            .order_by(desc(VlanTable.c.id))
            .limit(size + 1)  # Retrieve one more element to get the next token
        )
        if token is not None:
            stmt = stmt.where(le(VlanTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Vlan](
            items=[Vlan(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(self, id: int, resource: CreateOrUpdateResource) -> Vlan:
        raise NotImplementedError()

    async def delete(self, id: int) -> None:
        raise NotImplementedError()

    async def get_node_vlans(self, query: QuerySpec) -> List[Vlan]:
        """
        Returns all the vlans accessible by a node
        """

        stmt = (
            select(
                VlanTable,
            )
            .select_from(NodeTable)
            .join(
                NodeConfigTable,
                NodeTable.c.current_config_id == NodeConfigTable.c.id,
            )
            .join(
                InterfaceTable,
                NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
                isouter=True,
            )
            .join(
                InterfaceIPAddressTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
                isouter=True,
            )
            .join(
                StaticIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
                isouter=True,
            )
            .join(
                SubnetTable,
                SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
                isouter=True,
            )
            .join(
                VlanTable,
                or_(
                    VlanTable.c.id == SubnetTable.c.vlan_id,
                    VlanTable.c.id == InterfaceTable.c.vlan_id,
                ),
            )
            .where(query.where.condition)
        )
        result = (await self.connection.execute(stmt)).all()
        return [Vlan(**row._asdict()) for row in result]
