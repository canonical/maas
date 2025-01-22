#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import Connection, CursorResult, select
from sqlalchemy.sql.operators import eq

from maasservicelayer.context import Context
from maasservicelayer.db.tables import ConfigTable
from maasservicelayer.models.configurations import Configuration


class ConfigurationsRepository:
    def __init__(self, context: Context):
        self.connection = context.get_connection()

    # TODO: remove this when the connection in context is changed back to the
    # AsyncConnection type only.
    async def execute_stmt(self, stmt) -> CursorResult[Any]:
        """Execute the statement synchronously or asynchronously based on the
        type of the connection."""
        if isinstance(self.connection, Connection):
            return self.connection.execute(stmt)
        else:
            return await self.connection.execute(stmt)

    async def get(self, name: str) -> Configuration | None:
        stmt = (
            select(
                "*",
            )
            .select_from(ConfigTable)
            .where(eq(ConfigTable.c.name, name))
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        return Configuration(**result._asdict()) if result else None
