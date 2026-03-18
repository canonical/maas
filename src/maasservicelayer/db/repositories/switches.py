#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import func, Select, select, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceTable, SwitchTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.switches import Switch, SwitchWithTargetImage


class SwitchClauseFactory(ClauseFactory):
    """Factory for creating query clauses for Switch queries."""

    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SwitchTable.c.id, id))

    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=SwitchTable.c.id.in_(ids))


class SwitchesRepository(BaseRepository[Switch]):
    """Repository for managing Switch entities in the database."""

    def get_repository_table(self) -> Table:
        return SwitchTable

    def get_model_factory(self) -> Type[Switch]:
        return Switch

    @property
    def select_all_join_boot_resource(self) -> Select:
        return select(
            SwitchTable,
            BootResourceTable.c.name.label("target_image"),
        ).select_from(
            SwitchTable.outerjoin(
                BootResourceTable,
                SwitchTable.c.target_image_id == BootResourceTable.c.id,
            )
        )

    async def get_one_with_target_image(
        self, id: int
    ) -> SwitchWithTargetImage | None:
        stmt = self.select_all_join_boot_resource.where(SwitchTable.c.id == id)
        row = (await self.execute_stmt(stmt)).one_or_none()
        return (
            SwitchWithTargetImage(**row._asdict()) if row is not None else None
        )

    async def get_with_target_image(
        self, page: int, size: int
    ) -> ListResult[SwitchWithTargetImage]:
        total_stmt = select(func.count()).select_from(SwitchTable)
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = self.select_all_join_boot_resource.offset(
            (page - 1) * size
        ).limit(size)
        result = (await self.execute_stmt(stmt)).all()
        return ListResult(
            items=[SwitchWithTargetImage(**row._asdict()) for row in result],
            total=total,
        )
