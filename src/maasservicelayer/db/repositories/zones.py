#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import desc, func, select, Table
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    DefaultResourceTable,
    NodeTable,
    ZoneTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.zones import Zone, ZoneWithSummary


class ZonesClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=ZoneTable.c.id.in_(ids))


class ZonesRepository(BaseRepository[Zone]):
    def get_repository_table(self) -> Table:
        return ZoneTable

    def get_model_factory(self) -> Type[Zone]:
        return Zone

    async def get_default_zone(self) -> Zone:
        stmt = (
            select(ZoneTable)
            .select_from(ZoneTable)
            .join(
                DefaultResourceTable,
                eq(DefaultResourceTable.c.zone_id, ZoneTable.c.id),
            )
        )
        result = await self.execute_stmt(stmt)
        # By design the default zone is always present.
        zone = result.one()
        return Zone(**zone._asdict())

    async def list_with_summary(
        self, page: int, size: int
    ) -> ListResult[ZoneWithSummary]:
        total_stmt = select(count()).select_from(self.get_repository_table())
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            select(
                ZoneTable.c.id,
                ZoneTable.c.name,
                ZoneTable.c.description,
                func.count()
                .filter(NodeTable.c.node_type == NodeTypeEnum.DEVICE)
                .label("devices_count"),
                func.count()
                .filter(NodeTable.c.node_type == NodeTypeEnum.MACHINE)
                .label("machines_count"),
                func.count()
                .filter(
                    NodeTable.c.node_type.in_(
                        [
                            NodeTypeEnum.RACK_CONTROLLER,
                            NodeTypeEnum.REGION_CONTROLLER,
                            NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                        ]
                    )
                )
                .label("controllers_count"),
            )
            .select_from(
                ZoneTable.join(
                    NodeTable,
                    NodeTable.c.zone_id == ZoneTable.c.id,
                    isouter=True,
                )
            )
            .offset((page - 1) * size)
            .limit(size)
            .group_by(ZoneTable.c.id)
            .order_by(desc(ZoneTable.c.id))
        )

        result = await self.execute_stmt(stmt)
        return ListResult[ZoneWithSummary](
            items=[ZoneWithSummary(**row._asdict()) for row in result.all()],
            total=total,
        )
