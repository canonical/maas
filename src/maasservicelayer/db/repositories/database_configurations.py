# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.configurations import (
    DatabaseConfigurationBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import ConfigTable
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.configurations import DatabaseConfiguration


class DatabaseConfigurationsRepository(Repository[DatabaseConfiguration]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mapper = DefaultDomainDataMapper[DatabaseConfiguration](
            DatabaseConfiguration, ConfigTable
        )

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
        return self.mapper.to_domain(result._mapping)

    async def get_many(self, query: QuerySpec) -> list[DatabaseConfiguration]:
        stmt = select(
            "*",
        ).select_from(ConfigTable)
        stmt = self._translate(query).enrich_stmt(stmt)
        result = (await self.execute_stmt(stmt)).all()
        return [self.mapper.to_domain(row._mapping) for row in result]

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
        return self.mapper.to_domain(result._mapping)

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
        data = [
            {"name": key, "value": value}
            for key, value in configuration.items()
        ]
        stmt = pg_insert(ConfigTable).values(data).returning(ConfigTable)
        result = await self.execute_stmt(stmt)
        return [self.mapper.to_domain(row._mapping) for row in result.all()]
