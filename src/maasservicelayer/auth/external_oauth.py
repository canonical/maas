# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
from dataclasses import dataclass
from typing import Any

from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, JWTClaims, KeySet
from authlib.jose.errors import BadSignatureError
from httpx import HTTPStatusError
import structlog

from maascommon.logging.security import AUTHN_LOGIN_UNSUCCESSFUL, SECURITY
from maasservicelayer.auth.oidc_jwt import OAuthAccessToken, OAuthIDToken
from maasservicelayer.auth.token_cache import AccessTokenValidationCache
from maasservicelayer.exceptions.catalog import (
    BadGatewayException,
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
    PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
)
from maasservicelayer.models.external_auth import (
    AccessTokenType,
    OAuthProvider,
)
from maasservicelayer.utils.date import utcnow

JWKS_CACHE_TTL = 3600

logger = structlog.getLogger(__name__)


@dataclass
class OAuthInitiateData:
    authorization_url: str
    state: str
    nonce: str


@dataclass
class OAuthTokenData:
    access_token: OAuthAccessToken | str
    id_token: OAuthIDToken
    refresh_token: str


@dataclass
class OAuthUserData:
    sub: str
    email: str
    given_name: str | None
    family_name: str | None
    name: str | None


@dataclass
class OAuthCallbackData:
    tokens: OAuthTokenData
    user_info: OAuthUserData


@dataclass
class OAuthRefreshData:
    access_token: str
    refresh_token: str


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
        self._access_token_cache = AccessTokenValidationCache()

    def generate_authorization_url(
        self, redirect_target: str
    ) -> OAuthInitiateData:
        nonce = generate_token()
        state = self._generate_state(redirect_target=redirect_target)

        auth_url, state = self.client.create_authorization_url(
            url=self.provider.metadata.authorization_endpoint,
            state=state,
            nonce=nonce,
        )
        return OAuthInitiateData(
            authorization_url=auth_url,
            state=state,
            nonce=nonce,
        )

    def get_provider_name(self) -> str:
        return self.provider.name

    async def callback(self, code: str, nonce: str) -> OAuthCallbackData:
        try:
            tokens = await self._fetch_and_validate_tokens(
                code=code, nonce=nonce
            )

            user_info = await self.get_userinfo(
                access_token=tokens.access_token,
                id_token_claims=tokens.id_token.claims,
            )
            return OAuthCallbackData(
                tokens=tokens,
                user_info=user_info,
            )
        except Exception:
            logger.info(
                AUTHN_LOGIN_UNSUCCESSFUL,
                type=SECURITY,
            )
            raise

    async def get_userinfo(
        self, access_token: OAuthAccessToken | str, id_token_claims: JWTClaims
    ) -> OAuthUserData:
        allowed_keys = OAuthUserData.__annotations__.keys()

        # Try fetching claims from ID token first
        claims = {
            k: id_token_claims[k] for k in allowed_keys if k in id_token_claims
        }

        missing_keys = [k for k in allowed_keys if k not in claims]

        if not missing_keys:
            return OAuthUserData(**claims)

        token_str = (
            access_token
            if isinstance(access_token, str)
            else access_token.encoded
        )
        response = await self._userinfo_request(access_token=token_str)

        # Mandatory security check
        if response.get("sub") != id_token_claims.get("sub"):
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Claim 'sub' does not match ID token 'sub'.",
                    )
                ]
            )

        # Fill only missing claims from userinfo
        for k in missing_keys:
            if k in response:
                claims[k] = response[k]

        return OAuthUserData(
            sub=claims["sub"],
            email=claims["email"],
            given_name=claims.get("given_name", None),
            family_name=claims.get("family_name", None),
            name=claims.get("name", None),
        )

    async def validate_access_token(
        self, access_token: str
    ) -> OAuthAccessToken | str:
        """
        Validates an access token via JWT decoding, cache lookup, /introspection, or /userInfo fallback.
        """
        if self.provider.token_type == AccessTokenType.JWT:
            return OAuthAccessToken.from_token(
                provider=self.provider,
                encoded=access_token,
                jwks=await self._get_provider_jwks(),
            )
        # For opaque tokens, check cache first
        is_cached = await self._access_token_cache.is_valid(access_token)
        if is_cached:
            return access_token

        # If not cached, validate via introspection endpoint
        if self.provider.metadata.introspection_endpoint:
            await self._introspect_token(
                url=self.provider.metadata.introspection_endpoint,
                access_token=access_token,
            )
            await self._access_token_cache.add(access_token)
            return access_token

        # Fallback to userinfo endpoint validation, if no introspection endpoint
        try:
            await self._userinfo_request(access_token=access_token)
            await self._access_token_cache.add(access_token)
            return access_token
        except BadGatewayException as e:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                        message="Cannot validate access token: no userinfo or introspection endpoint available, and token is opaque.",
                    )
                ]
            ) from e

    async def revoke_token(self, token: str) -> None:
        revoke_url = self.provider.metadata.revocation_endpoint
        if revoke_url:
            await self._revoke_token(url=revoke_url, token=token)
        await self._access_token_cache.remove(token)

    async def parse_raw_id_token(self, id_token: str) -> OAuthIDToken:
        return OAuthIDToken.from_token(
            provider=self.provider,
            encoded=id_token,
            jwks=await self._get_provider_jwks(),
            skip_validation=True,
        )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> OAuthRefreshData:
        try:
            tokens = await self.client.refresh_token(
                url=self.provider.metadata.token_endpoint,
                refresh_token=refresh_token,
            )
        except HTTPStatusError as e:
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message="Failed to refresh tokens from OIDC server.",
                    )
                ]
            ) from e

        await self.validate_access_token(access_token=tokens["access_token"])
        # Some providers may return a new refresh token
        new_refresh_token = tokens.get("refresh_token", refresh_token)

        return OAuthRefreshData(
            access_token=tokens["access_token"],
            refresh_token=new_refresh_token,
        )

    def _generate_state(self, redirect_target: str) -> str:
        encoded = base64.urlsafe_b64encode(redirect_target.encode()).decode()
        random_str = generate_token()
        return f"{encoded}.{random_str}"

    async def _fetch_and_validate_tokens(
        self, code: str, nonce: str
    ) -> OAuthTokenData:
        try:
            token = await self.client.fetch_token(
                url=self.provider.metadata.token_endpoint,
                code=code,
                grant_type="authorization_code",
                redirect_uri=self.provider.redirect_uri,
            )
        except HTTPStatusError as e:
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message="Failed to fetch tokens from OIDC server.",
                    )
                ]
            ) from e

        if (
            not token.get("access_token")
            or not token.get("id_token")
            or not token.get("refresh_token")
        ):
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message="Invalid token response from OIDC server. Please ensure the provider is configured correctly.",
                    )
                ]
            )
        id_token = await self._validate_id_token(
            id_token=token["id_token"], nonce=nonce
        )
        access_token = await self.validate_access_token(
            access_token=token["access_token"]
        )
        return OAuthTokenData(
            access_token=access_token,
            id_token=id_token,
            refresh_token=token["refresh_token"],
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

    async def _introspect_token(self, url: str, access_token: str) -> None:
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
        result = response.json()
        if not result.get("active", False):
            await self._access_token_cache.remove(access_token)
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Access token is not active.",
                    )
                ]
            )

    async def _userinfo_request(self, access_token: str) -> dict[str, Any]:
        if self.provider.metadata.userinfo_endpoint:
            return await self._request(
                url=self.provider.metadata.userinfo_endpoint,
                access_token=access_token,
            )
        raise BadGatewayException(
            details=[
                BaseExceptionDetail(
                    type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                    message="Userinfo endpoint is not configured for the provider.",
                )
            ]
        )

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
        access_token: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        response = await self.client.get(url=url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _revoke_token(self, url: str, token: str) -> None:
        data = {
            "token": token,
            "token_type_hint": "refresh_token",
            "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret,
        }
        response = await self.client.post(url=url, data=data)
        response.raise_for_status()
