#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.operators import eq

from maasservicelayer.context import Context
from maasservicelayer.db.tables import SecretTable
from maasservicelayer.models.secrets import Secret


class SecretsRepository:
    def __init__(self, context: Context):
        self.connection = context.get_connection()

    async def create_or_update(self, path: str, value: dict[str, Any]) -> None:
        created_at = updated_at = datetime.datetime.now(datetime.timezone.utc)
        insert_stmt = insert(SecretTable).values(
            path=path, created=created_at, updated=updated_at, value=value
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SecretTable.c.path],
            set_=dict(updated=updated_at, value=value),
        )
        await self.connection.execute(upsert_stmt)

    async def get(self, path: str) -> Secret | None:
        stmt = (
            select("*")
            .select_from(SecretTable)
            .where(eq(SecretTable.c.path, path))
        )
        result = (await self.connection.execute(stmt)).one_or_none()
        return Secret(**result._asdict()) if result else None

    async def delete(self, path: str) -> None:
        await self.connection.execute(
            delete(SecretTable).where(eq(SecretTable.c.path, path))
        )
