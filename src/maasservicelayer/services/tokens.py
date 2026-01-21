# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import hashlib

from maasservicelayer.builders.tokens import (
    OIDCRevokedTokenBuilder,
    RefreshTokenBuilder,
    TokenBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tokens import (
    OIDCRevokedTokenRepository,
    RefreshTokenRepository,
    TokensRepository,
)
from maasservicelayer.models.configurations import RefreshTokenDurationConfig
from maasservicelayer.models.tokens import (
    OIDCRevokedToken,
    RefreshToken,
    Token,
)
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.utils.date import utcnow


class TokensService(BaseService[Token, TokensRepository, TokenBuilder]):
    """
    Piston3 Token service. See
    https://github.com/userzimmermann/django-piston3/blob/fe1ea644bcb07332670aeceddbf0ded29bdf785a/piston/models.py#L55 for
    reference.

    Remove this service once all the django and its OAuth method is removed from the codebase in favor of the new JWT approach.
    """

    def __init__(self, context: Context, repository: TokensRepository):
        super().__init__(context, repository)

    async def get_user_apikeys(self, username: str) -> list[str]:
        return await self.repository.get_user_apikeys(username)


class RefreshTokenService(
    BaseService[RefreshToken, RefreshTokenRepository, RefreshTokenBuilder]
):
    def __init__(
        self,
        context: Context,
        repository: RefreshTokenRepository,
        config_service: ConfigurationsService,
    ):
        self.config_service = config_service
        super().__init__(context, repository)

    async def create_refresh_token(
        self, token: str, user_id: int
    ) -> RefreshToken:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = utcnow() + timedelta(
            seconds=await self.config_service.get(
                RefreshTokenDurationConfig.name
            )
        )
        builder = RefreshTokenBuilder(
            user_id=user_id, token=token_hash, expires_at=expires_at
        )
        return await super().create(builder)


class OIDCRevokedTokenService(
    BaseService[
        OIDCRevokedToken, OIDCRevokedTokenRepository, OIDCRevokedTokenBuilder
    ]
):
    def __init__(
        self, context: Context, repository: OIDCRevokedTokenRepository
    ):
        super().__init__(context, repository)

    async def create_revoked_token(
        self, token: str, provider_id: int, email: str
    ):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        builder = OIDCRevokedTokenBuilder(
            provider_id=provider_id,
            user_email=email,
            token_hash=token_hash,
            revoked_at=utcnow(),
        )
        return await super().create(builder)
