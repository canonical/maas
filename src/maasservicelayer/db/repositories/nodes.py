#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from abc import ABC
from datetime import datetime
from typing import Any, Type, TypeVar

from sqlalchemy import Select, select, Table, update
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import BMCTable, NodeTable
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node


class NodeResourceBuilder(ResourceBuilder):
    def with_status(self, status: NodeStatus) -> "NodeResourceBuilder":
        self._request.set_value(NodeTable.c.status.name, status)
        return self

    def with_power_state(self, state: PowerState) -> "NodeResourceBuilder":
        self._request.set_value(NodeTable.c.power_state.name, state)
        return self

    def with_power_state_updated(
        self, timestamp: datetime
    ) -> "NodeResourceBuilder":
        self._request.set_value(
            NodeTable.c.power_state_updated.name, timestamp
        )
        return self


class NodeClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(NodeTable.c.id, id))

    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=NodeTable.c.id.in_(ids))

    @classmethod
    def with_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_type(cls, value: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, value))


T = TypeVar("T", bound=Node)


class AbstractNodesRepository(BaseRepository[T], ABC):

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(NodeTable)
            .where(eq(NodeTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)

    async def get_node_bmc(self, system_id: str) -> Bmc | None:
        stmt = self._bmc_select_all_statement().where(
            eq(NodeTable.c.system_id, system_id)
        )

        result = (await self.connection.execute(stmt)).one()
        return Bmc(**result._asdict())

    async def move_bmcs_to_zone(
        self, old_zone_id: int, new_zone_id: int
    ) -> None:
        stmt = (
            update(BMCTable)
            .where(eq(BMCTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)

    async def hostname_exists(self, hostname: str) -> bool:
        stmt = (
            select(NodeTable.c.id)
            .select_from(NodeTable)
            .filter(NodeTable.c.hostname == hostname)
        )

        exists = (await self.connection.execute(stmt)).one_or_none()

        return exists is not None

    def _bmc_select_all_statement(self) -> Select[Any]:
        # TODO: add other fields
        return (
            select(
                BMCTable.c.id,
                BMCTable.c.created,
                BMCTable.c.updated,
                BMCTable.c.power_type,
                BMCTable.c.power_parameters,
            )
            .select_from(BMCTable)
            .join(NodeTable, eq(NodeTable.c.bmc_id, BMCTable.c.id))
        )


class NodesRepository(AbstractNodesRepository[Node]):

    def get_repository_table(self) -> Table:
        return NodeTable

    def get_model_factory(self) -> Type[Node]:
        return Node
