# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import Any

from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, KeySet
from authlib.jose.errors import BadSignatureError
from httpx import HTTPStatusError

from maasservicelayer.auth.oidc_jwt import OAuthAccessToken, OAuthIDToken
from maasservicelayer.exceptions.catalog import (
    BadGatewayException,
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
)
from maasservicelayer.models.external_auth import OAuthProvider
from maasservicelayer.utils.date import utcnow

JWKS_CACHE_TTL = 3600


@dataclass
class OAuthInitiateData:
    authorization_url: str
    state: str
    nonce: str


class OAuth2Client:
    """
    Creates an OAuth2 Client that can interact with an external OIDC provider.
    """

    def __init__(self, provider: OAuthProvider):
        self.client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            redirect_uri=provider.redirect_uri,
            scope=provider.scopes,
        )
        self.provider = provider
        self._jwks_cache: KeySet | None = None
        self._jwks_cache_time: float = 0.0

    def generate_authorization_url(self) -> OAuthInitiateData:
        nonce = generate_token()

        auth_url, state = self.client.create_authorization_url(
            url=self.provider.metadata.authorization_endpoint,
            nonce=nonce,
        )
        return OAuthInitiateData(
            authorization_url=auth_url,
            state=state,
            nonce=nonce,
        )

    def get_provider_name(self) -> str:
        return self.provider.name

    async def validate_access_token(
        self, access_token: str
    ) -> OAuthAccessToken | str:
        """
        Validates an access token. If it's a JWT, verify locally. If opaque, use the introspection endpoint.
        """
        is_jwt = access_token.count(".") == 2
        if is_jwt:
            token = OAuthAccessToken.from_token(
                provider=self.provider,
                encoded=access_token,
                jwks=await self._get_provider_jwks(),
            )
            return token

        # Fallback: opaque token introspection
        if self.provider.metadata.introspection_endpoint:
            introspection = await self._introspect_token(
                url=self.provider.metadata.introspection_endpoint,
                access_token=access_token,
            )
            if not introspection.get("active", False):
                raise UnauthorizedException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_TOKEN_VIOLATION_TYPE,
                            message="Access token is not active.",
                        )
                    ]
                )
            return access_token
        raise UnauthorizedException(
            details=[
                BaseExceptionDetail(
                    type=INVALID_TOKEN_VIOLATION_TYPE,
                    message="Token is opaque and no introspection endpoint is configured.",
                )
            ]
        )

    async def _validate_id_token(
        self, id_token: str, nonce: str
    ) -> OAuthIDToken:
        try:
            return OAuthIDToken.from_token(
                provider=self.provider,
                encoded=id_token,
                jwks=await self._get_provider_jwks(),
                nonce=nonce,
            )
        except BadSignatureError:
            # Try with a fresh JWKS fetch in case of key rotation
            return OAuthIDToken.from_token(
                provider=self.provider,
                encoded=id_token,
                jwks=await self._get_provider_jwks(force_refresh=True),
                nonce=nonce,
            )

    async def _introspect_token(self, url: str, access_token: str):
        response = await self.client.introspect_token(
            url=url, token=access_token
        )
        if response.status_code != 200:
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message="Failed to introspect access token with OIDC server.",
                    )
                ]
            )
        return response.json()

    async def _get_provider_jwks(self, force_refresh: bool = False) -> KeySet:
        current_time = utcnow().timestamp()
        if (
            self._jwks_cache is not None
            and (current_time - self._jwks_cache_time) < JWKS_CACHE_TTL
            and not force_refresh
        ):
            return self._jwks_cache
        try:
            response = await self._request(
                url=f"{self.provider.metadata.jwks_uri}",
            )
        except HTTPStatusError as e:
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message="Failed to retrieve JWKS from OIDC server.",
                    )
                ]
            ) from e
        key_set = JsonWebKey.import_key_set(response)
        self._jwks_cache = key_set
        self._jwks_cache_time = current_time
        return key_set

    async def _request(
        self,
        url: str,
    ) -> dict[str, Any]:
        response = await self.client.get(url=url)
        response.raise_for_status()
        return response.json()
