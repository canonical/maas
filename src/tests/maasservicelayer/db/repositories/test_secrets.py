#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.secrets import (
    SecretsRepository,
    VaultSecretsRepository,
)
from maasservicelayer.db.tables import SecretTable, VaultSecretTable
from maasservicelayer.models.secrets import Secret
from tests.fixtures.factories.secret import create_test_secret
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSecretsRepository:
    async def test_create_or_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        secrets_repository = SecretsRepository(
            Context(connection=db_connection)
        )
        data = {"hello": "mate", "data": [1, 2, 3]}
        await secrets_repository.create_or_update(path="/mytest", value=data)

        [secret] = await fixture.get_typed(
            "maasserver_secret", Secret, eq(SecretTable.c.path, "/mytest")
        )
        assert secret.path == "/mytest"
        assert secret.value == data
        assert secret.updated is not None
        assert secret.created is not None

        await secrets_repository.create_or_update(
            path="/mytest", value="hello"
        )
        [updated_secret] = await fixture.get_typed(
            "maasserver_secret", Secret, eq(SecretTable.c.path, "/mytest")
        )
        assert updated_secret.value == "hello"
        assert updated_secret.created == secret.created
        assert updated_secret.updated >= secret.updated

    async def test_get(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_secret(fixture=fixture, path="/test", value="hello")
        secrets_repository = SecretsRepository(
            Context(connection=db_connection)
        )
        secret = await secrets_repository.get("/test")
        assert secret.value == "hello"
        assert secret.path == "/test"

    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_secret(fixture=fixture, path="/test", value="hello")
        secrets_repository = SecretsRepository(
            Context(connection=db_connection)
        )
        await secrets_repository.delete("/test")
        result = await fixture.get(
            "maasserver_secret", eq(SecretTable.c.path, "/test")
        )
        assert result == []


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestVaultSecretsRepository:
    async def test_create_or_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = VaultSecretsRepository(Context(connection=db_connection))
        await repository.create_or_update(path="/mytest")

        [entry] = await fixture.get(
            "maasserver_vaultsecret", eq(VaultSecretTable.c.path, "/mytest")
        )
        assert entry["path"] == "/mytest"
        assert entry["deleted"] is False

        await repository.mark_deleted("/mytest")
        [deleted_entry] = await fixture.get(
            "maasserver_vaultsecret", eq(VaultSecretTable.c.path, "/mytest")
        )
        assert deleted_entry["deleted"] is True

        # create_or_update resets the deleted flag.
        await repository.create_or_update(path="/mytest")
        [reset_entry] = await fixture.get(
            "maasserver_vaultsecret", eq(VaultSecretTable.c.path, "/mytest")
        )
        assert reset_entry["deleted"] is False

    async def test_get(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = VaultSecretsRepository(Context(connection=db_connection))
        assert await repository.get("/mytest") is None

        await repository.create_or_update(path="/mytest")
        entry = await repository.get("/mytest")
        assert entry is not None
        assert entry.path == "/mytest"
        assert entry.deleted is False

        await repository.mark_deleted("/mytest")
        deleted_entry = await repository.get("/mytest")
        assert deleted_entry is not None
        assert deleted_entry.deleted is True

    async def test_mark_deleted_missing_path_is_noop(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        repository = VaultSecretsRepository(Context(connection=db_connection))
        await repository.mark_deleted("/missing")
        result = await fixture.get(
            "maasserver_vaultsecret", eq(VaultSecretTable.c.path, "/missing")
        )
        assert result == []
