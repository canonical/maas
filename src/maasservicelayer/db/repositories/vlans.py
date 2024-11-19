#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List, Type

from sqlalchemy import select, Table
from sqlalchemy.sql.operators import eq, or_

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
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
from maasservicelayer.models.vlans import Vlan


class VlansClauseFactory(ClauseFactory):

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> Clause:
        return Clause(condition=eq(VlanTable.c.fabric_id, fabric_id))

    @classmethod
    def with_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_node_type(cls, type: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, type))


class VlanResourceBuilder(ResourceBuilder):
    def with_vid(self, vid: int) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.vid.name, vid)
        return self

    def with_name(self, name: str) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.name.name, name)
        return self

    def with_description(self, description: str) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.description.name, description)
        return self

    def with_mtu(self, mtu: int) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.mtu.name, mtu)
        return self

    def with_dhcp_on(self, dhcp_on: bool) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.dhcp_on.name, dhcp_on)
        return self

    def with_fabric_id(self, fabric_id: int) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.fabric_id.name, fabric_id)
        return self

    def with_primary_rack_id(
        self, primary_rack_id: int
    ) -> "VlanResourceBuilder":
        self._request.set_value(
            VlanTable.c.primary_rack_id.name, primary_rack_id
        )
        return self

    def with_secondary_rack_id(
        self, secondary_rack_id: int
    ) -> "VlanResourceBuilder":
        self._request.set_value(
            VlanTable.c.secondary_rack_id.name, secondary_rack_id
        )
        return self


class VlansRepository(BaseRepository[Vlan]):
    def get_repository_table(self) -> Table:
        return VlanTable

    def get_model_factory(self) -> Type[Vlan]:
        return Vlan

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
