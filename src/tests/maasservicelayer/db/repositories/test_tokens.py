# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.tokens import TokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import Clause, QuerySpec
from maasservicelayer.db.repositories.base import MultipleResultsException
from maasservicelayer.db.repositories.tokens import (
    TokenClauseFactory,
    TokensRepository,
)
from maasservicelayer.models.tokens import Token
from tests.fixtures.factories.consumer import create_test_user_consumer
from tests.fixtures.factories.token import create_test_user_token
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestTokenClauseFactory:
    def test_with_key(self) -> None:
        clause = TokenClauseFactory.with_key("key")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_token.key = 'key'")

    def test_with_secret(self) -> None:
        clause = TokenClauseFactory.with_secret("secret")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_token.secret = 'secret'")

    def test_with_consumer_id(self) -> None:
        clause = TokenClauseFactory.with_consumer_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_token.consumer_id = 1")

    def test_with_consumer_ids(self) -> None:
        clause = TokenClauseFactory.with_consumer_ids([1, 2])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_token.consumer_id IN (1, 2)")


class TestConsumersRepository(RepositoryCommonTests[Token]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> TokensRepository:
        return TokensRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Token]:
        user = await create_test_user(fixture)
        user_consumer = await create_test_user_consumer(fixture, user.id)
        return [
            await create_test_user_token(fixture, user.id, user_consumer.id)
            for _ in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Token:
        user = await create_test_user(fixture)
        user_consumer = await create_test_user_consumer(fixture, user.id)
        return await create_test_user_token(fixture, user.id, user_consumer.id)

    @pytest.fixture
    async def instance_builder_model(self) -> type[TokenBuilder]:
        return TokenBuilder

    @pytest.fixture
    async def instance_builder(self) -> TokenBuilder:
        return TokenBuilder(
            key="CtE9Cmy4asnRBtJvxQ",
            secret="DNPJDVa87vEesHE8sQ722yP6JJKnrem2",
            verifier="",
            token_type=2,
            timestamp=1725122700,
            is_approved=True,
            callback_confirmed=False,
            consumer_id=1,
            user_id=2,
        )

    @pytest.mark.skip(reason="Can't create a duplicated token")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    async def test_update_by_id(
        self,
        repository_instance: TokensRepository,
        instance_builder: TokenBuilder,
    ):
        created_resource = await repository_instance.create(instance_builder)
        updated_resource = await repository_instance.update_by_id(
            created_resource.id, TokenBuilder(key="newkey")
        )
        assert updated_resource.key == "newkey"

    async def test_update_one(
        self,
        repository_instance: TokensRepository,
        instance_builder: TokenBuilder,
    ):
        created_resource = await repository_instance.create(instance_builder)
        updated_resource = await repository_instance.update_one(
            QuerySpec(
                where=Clause(
                    eq(
                        repository_instance.get_repository_table().c.id,
                        created_resource.id,
                    )
                )
            ),
            TokenBuilder(key="newkey"),
        )
        assert updated_resource.key == "newkey"

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance: TokensRepository,
        instance_builder: TokenBuilder,
        _setup_test_list: Sequence[Token],
        num_objects: int,
    ):
        with pytest.raises(MultipleResultsException):
            await repository_instance.update_one(QuerySpec(), instance_builder)

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance: TokensRepository,
        _setup_test_list: Sequence[Token],
        num_objects: int,
    ):
        builder = TokenBuilder(key="newkey")
        updated_resources = await repository_instance.update_many(
            QuerySpec(), builder
        )
        assert len(updated_resources) == 2
        assert all(resource.key == "newkey" for resource in updated_resources)

    async def test_get_user_apikeys(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_consumer = await create_test_user_consumer(fixture, user.id)
        user_token = await create_test_user_token(
            fixture, user.id, user_consumer.id
        )

        apikey = ":".join(
            [user_consumer.key, user_token.key, user_token.secret]
        )

        tokens_repository = TokensRepository(Context(connection=db_connection))
        apikeys = await tokens_repository.get_user_apikeys(user.username)
        assert apikeys[0] == apikey
