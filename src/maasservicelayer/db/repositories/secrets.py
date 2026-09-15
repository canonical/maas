#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import SecretTable, VaultSecretTable
from maasservicelayer.models.secrets import Secret, VaultSecret


class SecretsRepository(Repository):
    async def create_or_update(self, path: str, value: dict[str, Any]) -> None:
        created_at = updated_at = datetime.datetime.now(datetime.timezone.utc)
        insert_stmt = insert(SecretTable).values(
            path=path, created=created_at, updated=updated_at, value=value
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[SecretTable.c.path],
            set_=dict(updated=updated_at, value=value),
        )
        await self.execute_stmt(upsert_stmt)

    async def get(self, path: str) -> Secret | None:
        stmt = (
            select("*")
            .select_from(SecretTable)
            .where(eq(SecretTable.c.path, path))
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        return Secret(**result._asdict()) if result else None

    async def delete(self, path: str) -> None:
        await self.execute_stmt(
            delete(SecretTable).where(eq(SecretTable.c.path, path))
        )


class VaultSecretsRepository(Repository):
    """Track the Vault secrets managed by MAAS.

    Deletions are not performed immediately in Vault: the secret is only
    marked for deletion here, and a recurrent cleanup job removes it from
    Vault asynchronously. This avoids accidental data loss if a transaction
    fails after the secret has been removed from Vault.
    """

    async def create_or_update(self, path: str) -> None:
        insert_stmt = insert(VaultSecretTable).values(path=path, deleted=False)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[VaultSecretTable.c.path],
            set_=dict(deleted=False),
        )
        await self.execute_stmt(upsert_stmt)

    async def get(self, path: str) -> VaultSecret | None:
        stmt = (
            select("*")
            .select_from(VaultSecretTable)
            .where(eq(VaultSecretTable.c.path, path))
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        return VaultSecret(**result._asdict()) if result else None

    async def mark_deleted(self, path: str) -> None:
        await self.execute_stmt(
            update(VaultSecretTable)
            .where(eq(VaultSecretTable.c.path, path))
            .values(deleted=True)
        )
