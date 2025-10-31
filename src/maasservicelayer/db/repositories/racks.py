# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import func, select, Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import AgentTable, NodeTable, RackTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.racks import Rack, RackWithSummary


class RacksClauseFactory(ClauseFactory):
    @classmethod
    def with_rack_id(cls, rack_id: int) -> Clause:
        return Clause(condition=eq(RackTable.c.id, rack_id))


class RacksRepository(BaseRepository[Rack]):
    def get_repository_table(self) -> Table:
        return RackTable

    def get_model_factory(self) -> type[Rack]:
        return Rack

    async def list_with_summary(
        self, page: int, size: int
    ) -> ListResult[RackWithSummary]:
        count_stmt = select(func.count()).select_from(RackTable)

        stmt = (
            select(
                RackTable.c.id,
                RackTable.c.name,
                func.array_agg(NodeTable.c.system_id).label(
                    "registered_agents_system_ids"
                ),
            )
            .select_from(RackTable)
            .outerjoin(AgentTable, AgentTable.c.rack_id == RackTable.c.id)
            .outerjoin(
                NodeTable, NodeTable.c.id == AgentTable.c.rackcontroller_id
            )
            .offset((page - 1) * size)
            .limit(size)
            .group_by(RackTable.c.id, RackTable.c.name)
        )

        result = await self.execute_stmt(stmt)
        total = (await self.execute_stmt(count_stmt)).scalar_one()
        return ListResult[RackWithSummary](
            items=[RackWithSummary(**row._asdict()) for row in result.all()],
            total=total,
        )
