# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tokens import TokensRepository
from maasservicelayer.models.tokens import Token
from maasservicelayer.services.tokens import TokensService
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_TOKEN = Token(
    id=0,
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


class TestCommonTokensService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> TokensService:
        return TokensService(
            context=Context(), repository=Mock(TokensRepository)
        )

    @pytest.fixture
    def test_instance(self) -> Token:
        return TEST_TOKEN

    async def test_get_user_apikeys(self) -> None:
        tokens_repository_mock = Mock(TokensRepository)
        tokens_service = TokensService(
            context=Context(), repository=tokens_repository_mock
        )
        await tokens_service.get_user_apikeys(username="username")
        tokens_repository_mock.get_user_apikeys.assert_called_once_with(
            "username"
        )
