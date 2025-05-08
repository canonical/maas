# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import select
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import ConfigTable
from maasservicelayer.models.configurations import DatabaseConfiguration


class DatabaseConfigurationsClauseFactory(ClauseFactory):
    @classmethod
    def with_names(cls, names: set[str]) -> Clause:
        return Clause(condition=ConfigTable.c.name.in_(names))


class DatabaseConfigurationsRepository(Repository):
    async def get(self, name: str) -> DatabaseConfiguration | None:
        stmt = (
            select(
                "*",
            )
            .select_from(ConfigTable)
            .where(eq(ConfigTable.c.name, name))
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        if result is None:
            return None
        return DatabaseConfiguration(**result._asdict())

    async def get_many(self, query: QuerySpec) -> list[DatabaseConfiguration]:
        stmt = select(
            "*",
        ).select_from(ConfigTable)
        stmt = query.enrich_stmt(stmt)
        result = (await self.execute_stmt(stmt)).all()
        return [DatabaseConfiguration(**row._asdict()) for row in result]
