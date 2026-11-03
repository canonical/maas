# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC
from typing import Any, Type, TypeVar

from sqlalchemy import Select, select, Table, update
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BMCTable, NodeTable
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node

T = TypeVar("T", bound=Node)


class AbstractNodesRepository(BaseRepository[T], ABC):
    async def get_url(self, system_id: str) -> str | None:
        stmt = select(NodeTable.c.url).where(
            NodeTable.c.system_id == system_id
        )
        return (await self.execute_stmt(stmt)).scalar_one_or_none()

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(NodeTable)
            .where(eq(NodeTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.execute_stmt(stmt)

    async def get_node_bmc(self, system_id: str) -> Bmc | None:
        stmt = self._bmc_select_all_statement().where(
            eq(NodeTable.c.system_id, system_id)
        )

        result = (await self.execute_stmt(stmt)).one()
        return Bmc(**result._asdict())

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
