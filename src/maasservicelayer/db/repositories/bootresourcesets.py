# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import List

from sqlalchemy import desc, Table

from maasservicelayer.db.filters import (
    Clause,
    ClauseFactory,
    OrderByClause,
    OrderByClauseFactory,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceSetTable
from maasservicelayer.models.bootresourcesets import BootResourceSet


class BootResourceSetClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: set[int]) -> Clause:
        return Clause(condition=BootResourceSetTable.c.id.in_(ids))

    @classmethod
    def with_resource_id(cls, resource_id: int) -> Clause:
        return Clause(
            condition=eq(BootResourceSetTable.c.resource_id, resource_id)
        )

    @classmethod
    def with_resource_ids(cls, resource_ids: list[int]) -> Clause:
        return Clause(
            condition=BootResourceSetTable.c.resource_id.in_(resource_ids)
        )

    @classmethod
    def with_version(cls, version: str) -> Clause:
        return Clause(condition=eq(BootResourceSetTable.c.version, version))

    @classmethod
    def with_version_prefix(cls, version: str) -> Clause:
        return Clause(
            condition=BootResourceSetTable.c.version.like(f"{version}%")
        )

    @classmethod
    def with_label(cls, label: str) -> Clause:
        return Clause(condition=eq(BootResourceSetTable.c.label, label))


class BootResourceSetsOrderByClauses(OrderByClauseFactory):
    @staticmethod
    def by_id() -> OrderByClause:
        return OrderByClause(column=BootResourceSetTable.c.id)


class BootResourceSetsRepository(BaseRepository[BootResourceSet]):
    def get_repository_table(self) -> Table:
        return BootResourceSetTable

    def get_model_factory(self) -> type[BootResourceSet]:
        return BootResourceSet

    async def get_latest_for_boot_resource(
        self, boot_resource_id: int
    ) -> BootResourceSet | None:
        stmt = (
            self.select_all_statement()
            .where(eq(BootResourceSetTable.c.resource_id, boot_resource_id))
            .order_by(desc(BootResourceSetTable.c.id))
            .limit(1)
        )
        result = (await self.execute_stmt(stmt)).all()
        if result:
            return BootResourceSet(**result[0]._asdict())
        return None

    async def get_many_newest_to_oldest_for_boot_resource(
        self, boot_resource_id: int
    ) -> List[BootResourceSet]:
        stmt = (
            self.select_all_statement()
            .where(eq(BootResourceSetTable.c.resource_id, boot_resource_id))
            .order_by(desc(BootResourceSetTable.c.id))
        )
        result = (await self.execute_stmt(stmt)).all()
        return [BootResourceSet(**row._asdict()) for row in result]
