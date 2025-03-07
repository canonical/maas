#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Type

from sqlalchemy import and_, desc, select, Table
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NodeTable, ResourcePoolTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.resource_pools import (
    ResourcePool,
    ResourcePoolWithSummary,
)


class ResourcePoolClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: Optional[list[int]]) -> Clause:
        return Clause(condition=ResourcePoolTable.c.id.in_(ids))


class ResourcePoolRepository(BaseRepository[ResourcePool]):
    def get_repository_table(self) -> Table:
        return ResourcePoolTable

    def get_model_factory(self) -> Type[ResourcePool]:
        return ResourcePool

    async def list_ids(self) -> set[int]:
        stmt = select(ResourcePoolTable.c.id).select_from(ResourcePoolTable)
        result = (await self.execute_stmt(stmt)).all()
        return {row.id for row in result}

    async def list_with_summary(
        self, page: int, size: int, query: QuerySpec | None
    ) -> ListResult[ResourcePoolWithSummary]:
        total_stmt = select(func.count()).select_from(
            self.get_repository_table()
        )
        if query:
            total_stmt = query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar()

        stmt = (
            select(
                ResourcePoolTable.c.id,
                ResourcePoolTable.c.name,
                ResourcePoolTable.c.description,
                func.count()
                .filter(eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE))
                .label("machine_total_count"),
                func.count()
                .filter(
                    and_(
                        eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE),
                        eq(NodeTable.c.status, NodeStatus.READY),
                    )
                )
                .label("machine_ready_count"),
            )
            .select_from(
                ResourcePoolTable.join(
                    NodeTable,
                    NodeTable.c.pool_id == ResourcePoolTable.c.id,
                    isouter=True,
                )
            )
            .offset((page - 1) * size)
            .limit(size)
            .group_by(ResourcePoolTable.c.id)
            .order_by(desc(ResourcePoolTable.c.id))
        )
        if query:
            stmt = query.enrich_stmt(stmt)

        result = await self.execute_stmt(stmt)
        return ListResult[ResourcePoolWithSummary](
            items=[
                ResourcePoolWithSummary(**row._asdict())
                for row in result.all()
            ],
            total=total,
        )
