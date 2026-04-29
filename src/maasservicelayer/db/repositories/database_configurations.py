# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import Connection, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.configurations import (
    DatabaseConfigurationBuilder,
)
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import ConfigTable
from maasservicelayer.models.configurations import DatabaseConfiguration


class DatabaseConfigurationsClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(ConfigTable.c.name, name))

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

    async def create_or_update(
        self, builder: DatabaseConfigurationBuilder
    ) -> DatabaseConfiguration:
        upsert_stmt = (
            pg_insert(ConfigTable)
            .values(name=builder.name, value=builder.value)
            .on_conflict_do_update(
                index_elements=[ConfigTable.c.name],
                set_=dict(value=builder.value),
            )
            .returning(ConfigTable)
        )
        result = (await self.execute_stmt(upsert_stmt)).one()
        return DatabaseConfiguration(**result._asdict())

    async def clear(self) -> None:
        await self.execute_stmt(delete(ConfigTable))

    async def set_many(
        self, configuration: dict[str, Any]
    ) -> list[DatabaseConfiguration]:
        """
        Set many configuration items at once.
        Args:
            configuration: The configuration to set in the database. Keys of
            this dict are the names of the configuration items.
        """
        connection = self.context.get_connection()
        stmt = pg_insert(ConfigTable).returning(ConfigTable)
        data = [
            {"name": key, "value": value}
            for key, value in configuration.items()
        ]
        if isinstance(connection, Connection):
            result = connection.execute(stmt, data)
        else:
            result = await connection.execute(stmt, data)
        return [DatabaseConfiguration(**row._asdict()) for row in result.all()]
