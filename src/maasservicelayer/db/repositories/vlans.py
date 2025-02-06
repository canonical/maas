#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List, Type

from sqlalchemy import select, Table
from sqlalchemy.sql.operators import eq, or_

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    SubnetTable,
    VlanTable,
)
from maasservicelayer.models.vlans import Vlan


class VlansClauseFactory(ClauseFactory):

    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(VlanTable.c.id, id))

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> Clause:
        return Clause(condition=eq(VlanTable.c.fabric_id, fabric_id))

    @classmethod
    def with_space_id(cls, space_id: int) -> Clause:
        return Clause(condition=eq(VlanTable.c.space_id, space_id))

    @classmethod
    def with_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, type))


class VlansRepository(BaseRepository[Vlan]):
    def get_repository_table(self) -> Table:
        return VlanTable

    def get_model_factory(self) -> Type[Vlan]:
        return Vlan

    async def get_fabric_default_vlan(self, fabric_id: int) -> Vlan:
        # Same logic of maasserver.models.fabric.Fabric.get_default_vlan.
        stmt = (
            self.select_all_statement()
            .where(eq(VlanTable.c.fabric_id, fabric_id))
            .order_by(VlanTable.c.id)
            .limit(1)
        )
        result = (await self.execute_stmt(stmt)).one()
        return self.get_model_factory()(**result._asdict())

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
        )
        stmt = query.enrich_stmt(stmt)
        result = (await self.execute_stmt(stmt)).all()
        return [Vlan(**row._asdict()) for row in result]
