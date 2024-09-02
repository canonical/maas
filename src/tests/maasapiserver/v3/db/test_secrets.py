import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasapiserver.v3.db.secrets import SecretsRepository
from maasservicelayer.db.tables import SecretTable
from maasservicelayer.models.secrets import Secret
from tests.fixtures.factories.secret import create_test_secret
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSecretsRepository:
    async def test_create_or_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        secrets_repository = SecretsRepository(db_connection)
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
        secrets_repository = SecretsRepository(db_connection)
        secret = await secrets_repository.get("/test")
        assert secret.value == "hello"
        assert secret.path == "/test"

    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_secret(fixture=fixture, path="/test", value="hello")
        secrets_repository = SecretsRepository(db_connection)
        await secrets_repository.delete("/test")
        result = await fixture.get(
            "maasserver_secret", eq(SecretTable.c.path, "/test")
        )
        assert result == []
