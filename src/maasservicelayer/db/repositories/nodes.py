#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC
from typing import Any, Type, TypeVar

from sqlalchemy import Select, select, Table, update
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BMCTable, NodeTable
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node
from maasservicelayer.utils.date import utcnow


class NodeClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(NodeTable.c.id, id))

    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=NodeTable.c.id.in_(ids))

    @classmethod
    def with_hostname(cls, hostname: str | None) -> Clause:
        return Clause(condition=eq(NodeTable.c.hostname, hostname))

    @classmethod
    def with_system_id(cls, system_id: str) -> Clause:
        return Clause(condition=eq(NodeTable.c.system_id, system_id))

    @classmethod
    def with_type(cls, value: NodeTypeEnum) -> Clause:
        return Clause(condition=eq(NodeTable.c.node_type, value))

    @classmethod
    def with_owner_id(cls, owner_id: int) -> Clause:
        return Clause(condition=eq(NodeTable.c.owner_id, owner_id))

    @classmethod
    def with_node_config_id(cls, node_config_id: int) -> Clause:
        return Clause(
            condition=eq(NodeTable.c.current_config_id, node_config_id)
        )


T = TypeVar("T", bound=Node)


class AbstractNodesRepository(BaseRepository[T], ABC):
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

    async def move_bmcs_to_zone(
        self, old_zone_id: int, new_zone_id: int
    ) -> None:
        stmt = (
            update(BMCTable)
            .where(eq(BMCTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.execute_stmt(stmt)

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

    async def update_node_bmc(
        self, system_id: str, power_type: str, power_parameters: dict
    ) -> Bmc:
        """Update power_type and power_parameters for the BMC of `system_id`.

        Raises :class:`NotFoundException` if the node has no linked BMC.
        """
        bmc_id_subquery = (
            select(NodeTable.c.bmc_id)
            .where(eq(NodeTable.c.system_id, system_id))
            .scalar_subquery()
        )
        stmt = (
            update(BMCTable)
            .where(BMCTable.c.id == bmc_id_subquery)
            .values(
                power_type=power_type,
                power_parameters=power_parameters,
                updated=utcnow(),
            )
            .returning(
                BMCTable.c.id,
                BMCTable.c.created,
                BMCTable.c.updated,
                BMCTable.c.power_type,
                BMCTable.c.power_parameters,
            )
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        if result is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"No BMC found for machine {system_id!r}.",
                    )
                ]
            )
        return Bmc(**result._asdict())


class NodesRepository(AbstractNodesRepository[Node]):
    def get_repository_table(self) -> Table:
        return NodeTable

    def get_model_factory(self) -> Type[Node]:
        return Node
