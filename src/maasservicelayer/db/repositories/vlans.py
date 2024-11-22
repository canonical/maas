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
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.vlans import Vlan

DEFAULT_MTU = 1500


class VlansClauseFactory(ClauseFactory):

    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(VlanTable.c.id, id))

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
        if vid < 0 or vid > 4094:
            raise ValidationException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="The VLAN VID must be within the range [0, 4094].",
                    )
                ]
            )
        self._request.set_value(VlanTable.c.vid.name, vid)
        return self

    def with_name(self, name: str | None = None) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.name.name, name)
        return self

    def with_description(
        self, description: str | None = None
    ) -> "VlanResourceBuilder":
        if not description:
            # inherited from the django model where it's optional in the request and empty by default.
            description = ""
        self._request.set_value(VlanTable.c.description.name, description)
        return self

    def with_mtu(self, mtu: int | None = None) -> "VlanResourceBuilder":
        if mtu is not None and (mtu < 552 or mtu > 65535):
            raise ValidationException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="The MTU must be within the range [552,65535].",
                    )
                ]
            )
        self._request.set_value(VlanTable.c.mtu.name, mtu or DEFAULT_MTU)
        return self

    def with_dhcp_on(self, dhcp_on: bool) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.dhcp_on.name, dhcp_on)
        return self

    def with_fabric_id(self, fabric_id: int) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.fabric_id.name, fabric_id)
        return self

    def with_space_id(
        self, space_id: int | None = None
    ) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.space_id.name, space_id)
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

    def with_relay_vlan_id(self, relay_vlan_id: int) -> "VlanResourceBuilder":
        self._request.set_value(VlanTable.c.relay_vlan_id.name, relay_vlan_id)
        return self


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
            .order_by(VlanTable.c.fabric_id)
            .limit(1)
        )
        result = (await self.connection.execute(stmt)).one()
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
        result = (await self.connection.execute(stmt)).all()
        return [Vlan(**row._asdict()) for row in result]
