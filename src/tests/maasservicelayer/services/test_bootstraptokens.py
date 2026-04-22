# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import call, Mock, patch

import pytest

from maascommon.logging.security import (
    AUTHN_TOKEN_CREATED,
    AUTHN_TOKEN_DELETED,
    hash_token_for_logging,
    SECURITY,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensRepository,
)
from maasservicelayer.models.bootstraptokens import BootstrapToken
from maasservicelayer.services.bootstraptoken import BootstrapTokensService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootstrapTokenService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootstrapTokensService:
        return BootstrapTokensService(
            context=Context(), repository=Mock(BootstrapTokensRepository)
        )

    @pytest.fixture
    def test_instance(self) -> BootstrapToken:
        one_month_from_now = utcnow() + timedelta(days=30)
        return BootstrapToken(
            id=1, expires_at=one_month_from_now, secret="secret", rack_id=1
        )

    async def test_post_create_hook(
        self, test_instance: BootstrapToken
    ) -> None:
        token = test_instance

        service = BootstrapTokensService(
            context=Context(), repository=Mock(BootstrapTokensRepository)
        )

        with patch(
            "maasservicelayer.services.bootstraptoken.logger"
        ) as mock_logger:
            await service.post_create_hook(token)

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_CREATED}:bootstraptoken",
            type=SECURITY,
            token_hash=hash_token_for_logging(token.secret),
        )

    async def test_post_create_many_hook(
        self, test_instance: BootstrapToken
    ) -> None:
        one_month_from_now = utcnow() + timedelta(days=30)
        tokens = [
            test_instance,
            BootstrapToken(
                id=2,
                expires_at=one_month_from_now,
                secret="secret2",
                rack_id=1,
            ),
            BootstrapToken(
                id=3,
                expires_at=one_month_from_now,
                secret="secret3",
                rack_id=2,
            ),
        ]

        service = BootstrapTokensService(
            context=Context(), repository=Mock(BootstrapTokensRepository)
        )

        with patch(
            "maasservicelayer.services.bootstraptoken.logger"
        ) as mock_logger:
            await service.post_create_many_hook(tokens)

        assert mock_logger.info.call_count == 3
        mock_logger.info.assert_has_calls(
            [
                call(
                    f"{AUTHN_TOKEN_CREATED}:bootstraptoken",
                    type=SECURITY,
                    token_hash=hash_token_for_logging(token.secret),
                )
                for token in tokens
            ]
        )

    async def test_post_delete_hook(
        self, test_instance: BootstrapToken
    ) -> None:
        token = test_instance

        service = BootstrapTokensService(
            context=Context(), repository=Mock(BootstrapTokensRepository)
        )

        with patch(
            "maasservicelayer.services.bootstraptoken.logger"
        ) as mock_logger:
            await service.post_delete_hook(token)

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_DELETED}:bootstraptoken",
            type=SECURITY,
            token_hash=hash_token_for_logging(token.secret),
        )

    async def test_post_delete_many_hook(
        self, test_instance: BootstrapToken
    ) -> None:
        one_month_from_now = utcnow() + timedelta(days=30)
        tokens = [
            test_instance,
            BootstrapToken(
                id=2,
                expires_at=one_month_from_now,
                secret="secret2",
                rack_id=1,
            ),
            BootstrapToken(
                id=3,
                expires_at=one_month_from_now,
                secret="secret3",
                rack_id=2,
            ),
        ]

        service = BootstrapTokensService(
            context=Context(), repository=Mock(BootstrapTokensRepository)
        )

        with patch(
            "maasservicelayer.services.bootstraptoken.logger"
        ) as mock_logger:
            await service.post_delete_many_hook(tokens)

        assert mock_logger.info.call_count == 3
        mock_logger.info.assert_has_calls(
            [
                call(
                    f"{AUTHN_TOKEN_DELETED}:bootstraptoken",
                    type=SECURITY,
                    token_hash=hash_token_for_logging(token.secret),
                )
                for token in tokens
            ]
        )
