#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

import structlog

from maascommon.logging.security import (
    AUTHN_TOKEN_CREATED,
    AUTHN_TOKEN_REUSED,
    AUTHN_TOKEN_REVOKED,
    hash_token_for_logging,
    SECURITY,
)
from maasservicelayer.builders.tokens import ApiTokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.api_tokens import (
    ApiTokenClauseFactory,
    ApiTokenRepository,
)
from maasservicelayer.models.tokens import ApiToken
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.api_tokens import (
    floor_to_throttle_window,
    generate_api_token,
    parse_api_token,
    secret_matches,
)
from maasservicelayer.utils.date import utcnow

logger = structlog.getLogger()


class ApiTokenService(
    BaseService[ApiToken, ApiTokenRepository, ApiTokenBuilder]
):
    def __init__(self, context: Context, repository: ApiTokenRepository):
        super().__init__(context, repository)

    async def create_token(
        self, user_id: int, name: str, expires_at: datetime
    ) -> tuple[ApiToken, str]:
        """Create a token. The raw token is only available from here."""
        generated = generate_api_token()
        token = await super().create(
            ApiTokenBuilder(
                name=name,
                public_id=generated.public_id,
                secret_hash=generated.secret_hash,
                expires_at=expires_at,
                user_id=user_id,
            )
        )
        logger.info(
            f"{AUTHN_TOKEN_CREATED}:PAT",
            type=SECURITY,
            token_hash=hash_token_for_logging(generated.raw_token),
        )
        return token, generated.raw_token

    # The generic create would accept a caller-chosen secret_hash and skip
    # generating the secret, so tokens must come from create_token.
    async def create(self, builder):
        raise NotImplementedError(
            "Create is not supported for API tokens. Use create_token instead."
        )

    async def authenticate(self, raw_token: str) -> ApiToken | None:
        """Return the token if valid, not expired and not revoked."""
        parsed = parse_api_token(raw_token)
        token = None
        if parsed:
            public_id, secret = parsed
            token = await self.get_one(
                QuerySpec(
                    where=ApiTokenClauseFactory.with_public_id(public_id)
                )
            )
            if token and not secret_matches(secret, token.secret_hash):
                token = None
        if (
            token is None
            or token.revoked_at is not None
            or token.expires_at <= utcnow()
        ):
            logger.info(
                f"{AUTHN_TOKEN_REUSED}:PAT",
                type=SECURITY,
                token_hash=hash_token_for_logging(raw_token),
            )
            return None
        return await self._touch_last_used(token)

    async def _touch_last_used(self, token: ApiToken) -> ApiToken:
        window_start = floor_to_throttle_window(utcnow())
        if token.last_used_at is not None and (
            token.last_used_at >= window_start
        ):
            return token
        return await self.repository.update_by_id(
            token.id, ApiTokenBuilder(last_used_at=window_start)
        )

    async def revoke(self, token: ApiToken) -> ApiToken:
        if token.revoked_at is not None:
            return token
        revoked = await self.repository.update_by_id(
            token.id, ApiTokenBuilder(revoked_at=utcnow())
        )
        logger.info(
            f"{AUTHN_TOKEN_REVOKED}:PAT",
            type=SECURITY,
            token_id=token.id,
            user_id=token.user_id,
        )
        return revoked
