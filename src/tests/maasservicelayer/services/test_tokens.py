# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from maasservicelayer.builders.tokens import OIDCRevokedTokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tokens import (
    OIDCRevokedTokenRepository,
    TokensRepository,
)
from maasservicelayer.models.tokens import OIDCRevokedToken, Token
from maasservicelayer.services.tokens import (
    OIDCRevokedTokenService,
    TokensService,
)
from maasservicelayer.utils.date import utcnow
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

TEST_REVOKED_TOKEN = OIDCRevokedToken(
    id=1,
    token_hash="abc123",
    revoked_at=utcnow(),
    provider_id=1,
    user_email="user@example.com",
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


@pytest.mark.asyncio
class TestRevokedTokensService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> OIDCRevokedTokenService:
        return OIDCRevokedTokenService(
            context=Context(), repository=Mock(OIDCRevokedTokenRepository)
        )

    @pytest.fixture
    def test_instance(self) -> OIDCRevokedToken:
        return TEST_REVOKED_TOKEN

    @patch("maasservicelayer.services.tokens.hashlib.sha256")
    @patch(
        "maasservicelayer.services.base.BaseService.create",
        new_callable=AsyncMock,
    )
    @patch("maasservicelayer.services.tokens.utcnow")
    async def test_create_revoked_token(
        self,
        mock_utcnow: MagicMock,
        mock_base_create: AsyncMock,
        mock_sha256: MagicMock,
        service_instance: OIDCRevokedTokenService,
    ) -> None:
        mock_utcnow.return_value = utcnow()
        mock_hash = Mock()
        mock_hash.hexdigest.return_value = "abc123"
        mock_sha256.return_value = mock_hash
        mock_base_create.return_value = TEST_REVOKED_TOKEN
        builder = OIDCRevokedTokenBuilder(
            provider_id=1,
            user_email="test@example.com",
            token_hash="abc123",
            revoked_at=mock_utcnow.return_value,
        )

        created = await service_instance.create_revoked_token(
            token="raw_token", provider_id=1, email="test@example.com"
        )

        mock_base_create.assert_awaited_once_with(builder)
        assert created.token_hash == "abc123"
