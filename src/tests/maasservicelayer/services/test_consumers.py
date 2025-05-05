# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.consumers import ConsumersRepository
from maasservicelayer.db.repositories.tokens import TokenClauseFactory
from maasservicelayer.models.consumers import Consumer
from maasservicelayer.services import ConsumersService, TokensService
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_CONSUMER = Consumer(
    id=1,
    name="myconsumername",
    description="myconsumerdescription",
    key="cqJF8TCX9gZw8SZpNr",
    secret="",
    status="accepted",
    user_id=1,
)


class TestCommonConsumersService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> ConsumersService:
        return ConsumersService(
            context=Context(),
            repository=Mock(ConsumersRepository),
            tokens_service=Mock(TokensService),
        )

    @pytest.fixture
    def test_instance(self) -> Consumer:
        return TEST_CONSUMER

    async def test_post_delete_one_cascades_tokens(
        self, service_instance: ConsumersService
    ):
        service_instance.repository.get_by_id.return_value = TEST_CONSUMER
        service_instance.repository.delete_by_id.return_value = TEST_CONSUMER
        service_instance.tokens_service.delete_many.return_value = []
        obj = await service_instance.delete_by_id(1)
        assert obj == TEST_CONSUMER
        service_instance.repository.get_by_id.assert_awaited_once_with(id=1)
        service_instance.repository.delete_by_id.assert_awaited_once_with(id=1)
        service_instance.tokens_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=TokenClauseFactory.with_consumer_id(TEST_CONSUMER.id)
            )
        )

    async def test_post_delete_many_cascades_tokens(
        self, service_instance: ConsumersService
    ):
        service_instance.repository.delete_many.return_value = [TEST_CONSUMER]
        service_instance.tokens_service.delete_many.return_value = []
        query = QuerySpec()
        objs = await service_instance.delete_many(query)
        assert objs == [TEST_CONSUMER]
        service_instance.repository.delete_many.assert_awaited_once_with(
            query=query
        )
        service_instance.tokens_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=TokenClauseFactory.with_consumer_ids([TEST_CONSUMER.id])
            )
        )
