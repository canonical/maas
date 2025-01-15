#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sslkeys import (
    SSLKeyClauseFactory,
    SSLKeyResourceBuilder,
    SSLKeysRepository,
)
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.utils.date import utcnow
from tests.fixtures import get_test_data_file
from tests.fixtures.factories.sslkey import create_test_sslkey
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSSLKeyClauseFactory:
    def test_builder(self) -> None:
        clause = SSLKeyClauseFactory.with_user_id(user_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_sslkey.user_id = 1")

        clause = SSLKeyClauseFactory.with_id(id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_sslkey.id = 1")


class TestSSLKeyResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        key = get_test_data_file("test_x509_0.pem")

        resource = (
            SSLKeyResourceBuilder()
            .with_key(key)
            .with_created(now)
            .with_updated(now)
            .with_user_id(0)
            .build()
        )

        assert resource.get_values() == {
            "key": key,
            "created": now,
            "updated": now,
            "user_id": 0,
        }


class TestSSLKeyRepository(RepositoryCommonTests[SSLKey]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SSLKeysRepository:
        return SSLKeysRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[SSLKey]:
        created_sslkeys = [
            # NOTE: If RepositoryCommonTests:test_list changes to use
            # more num_objects > 10, add more .pem test data files.
            (
                await create_test_sslkey(
                    fixture=fixture,
                    key=get_test_data_file(f"test_x509_{i}.pem"),
                )
            )
            for i in range(0, num_objects)
        ]
        return created_sslkeys

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> SSLKey:
        return await create_test_sslkey(fixture=fixture)

    @pytest.fixture
    async def instance_builder(self):  # -> SSLKeyResourceBuilder
        raise NotImplementedError("Not implemented yet.")

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Does not apply to SSL keys")
    async def test_update_by_id(self, repository_instance, instance_builder):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to SSL keys")
    async def test_update_one(self, repository_instance, instance_builder):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to SSL keys")
    async def test_update_one_multiple_results(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Does not apply to SSL keys")
    async def test_update_many(self, repository_instance, instance_builder):
        raise NotImplementedError()
