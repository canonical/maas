#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import select
from sqlalchemy.sql.operators import eq

from maasservicelayer.context import Context
from maasservicelayer.db.tables import ConfigTable
from maasservicelayer.models.configurations import Configuration


class ConfigurationsRepository:
    def __init__(self, context: Context):
        self.connection = context.get_connection()

    async def get(self, name: str) -> Configuration | None:
        stmt = (
            select(
                "*",
            )
            .select_from(ConfigTable)
            .where(eq(ConfigTable.c.name, name))
        )
        result = (await self.connection.execute(stmt)).one_or_none()
        return Configuration(**result._asdict()) if result else None
