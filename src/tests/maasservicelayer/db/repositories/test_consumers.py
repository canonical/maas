# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.consumers import ConsumerBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import Clause, QuerySpec
from maasservicelayer.db.repositories.base import MultipleResultsException
from maasservicelayer.db.repositories.consumers import (
    ConsumerClauseFactory,
    ConsumersRepository,
)
from maasservicelayer.models.consumers import Consumer
from tests.fixtures.factories.consumer import create_test_user_consumer
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestConsumerClauseFactory:
    def test_with_key(self) -> None:
        clause = ConsumerClauseFactory.with_key("key")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_consumer.key = 'key'")

    def test_with_secret(self) -> None:
        clause = ConsumerClauseFactory.with_secret("secret")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_consumer.secret = 'secret'")

    def test_with_user_id(self) -> None:
        clause = ConsumerClauseFactory.with_user_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("piston3_consumer.user_id = 1")


class TestConsumersRepository(RepositoryCommonTests[Consumer]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ConsumersRepository:
        return ConsumersRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Consumer]:
        user = await create_test_user(fixture)
        return [
            await create_test_user_consumer(
                fixture,
                name=f"foo-{i}",
                user_id=user.id,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Consumer:
        user = await create_test_user(fixture)
        return await create_test_user_consumer(
            fixture,
            name="foo",
            user_id=user.id,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ConsumerBuilder]:
        return ConsumerBuilder

    @pytest.fixture
    async def instance_builder(self) -> ConsumerBuilder:
        return ConsumerBuilder(
            name="bar",
            description="mydescription",
            key="cqJF8TCX9gZw8SZpNr",
            secret="",
            status="accepted",
            user_id=1,
        )

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    async def test_update_by_id(
        self,
        repository_instance: ConsumersRepository,
        instance_builder: ConsumerBuilder,
    ):
        created_resource = await repository_instance.create(instance_builder)
        updated_resource = await repository_instance.update_by_id(
            created_resource.id,
            ConsumerBuilder(name=created_resource.name + "new"),
        )
        assert updated_resource.name == created_resource.name + "new"

    async def test_update_one(
        self,
        repository_instance: ConsumersRepository,
        instance_builder: ConsumerBuilder,
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
            ConsumerBuilder(name=created_resource.name + "new"),
        )
        assert updated_resource.name == created_resource.name + "new"

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance: ConsumersRepository,
        instance_builder: ConsumerBuilder,
        _setup_test_list: Sequence[Consumer],
        num_objects: int,
    ):
        with pytest.raises(MultipleResultsException):
            await repository_instance.update_one(QuerySpec(), instance_builder)

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance: ConsumersRepository,
        _setup_test_list: Sequence[Consumer],
        num_objects: int,
    ):
        builder = ConsumerBuilder(name="foonew")
        updated_resources = await repository_instance.update_many(
            QuerySpec(), builder
        )
        assert len(updated_resources) == 2
        assert all(resource.name == "foonew" for resource in updated_resources)
