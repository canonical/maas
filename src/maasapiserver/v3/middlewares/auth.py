# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import abc
from typing import Awaitable, Callable, Dict, Sequence

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

from maasapiserver.v3.auth.cookie_manager import (
    EncryptedCookieManager,
    MAASLocalCookie,
    MAASOAuth2Cookie,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.logging.security import (
    ACCESS_TOKEN,
    AUTHN_AUTH_FAILED,
    AUTHN_AUTH_SUCCESSFUL,
    AUTHN_TOKEN_CREATED,
    AUTHN_TOKEN_REUSED,
    hash_token_for_logging,
    REFRESH_TOKEN,
    SECURITY,
)
from maascommon.utils.jwt import decode_unverified_jwt, JWTDecodeError
from maasservicelayer.auth.external_oauth import OAuthRefreshData
from maasservicelayer.auth.jwt import InvalidToken, JWT
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    NOT_AUTHENTICATED_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.users import User

logger = structlog.getLogger()


class AuthenticationProvider(abc.ABC):
    @abc.abstractmethod
    async def authenticate(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        """
        Returns the authenticated user. Raise an exception if the token is not valid, is expired or is invalid.
        """
        pass


class JWTAuthenticationProvider(AuthenticationProvider, abc.ABC):
    @classmethod
    @abc.abstractmethod
    def get_issuer(cls):
        """
        Returns the issuer of this authentication provider.
        """
        raise NotImplementedError()


class LocalAuthenticationProvider(JWTAuthenticationProvider):
    async def authenticate(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        refresh_token = request.state.cookie_manager.get_unsafe_cookie(
            MAASLocalCookie.REFRESH_TOKEN
        )
        try:
            jwt_token = (
                await request.state.services.auth.decode_and_verify_token(
                    token
                )
            )
            return AuthenticatedUser(
                id=jwt_token.user_id,
                username=jwt_token.subject,
            )
        except InvalidToken:
            # Use refresh token to get a new JWT if the JWT is expired.
            if not refresh_token:
                logger.info(
                    f"{AUTHN_TOKEN_REUSED}:JWT:{ACCESS_TOKEN}",
                    type=SECURITY,
                    token_hash=hash_token_for_logging(token),
                )
                raise UnauthorizedException(  # noqa: B904
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_TOKEN_VIOLATION_TYPE,
                            message="The token is not valid, and no refresh token is present.",
                        )
                    ]
                )
            user = await self._get_user_if_valid_token(
                request, refresh_token.strip()
            )
            new_token = await self._get_new_jwt(request, user)
            logger.info(
                f"{AUTHN_TOKEN_CREATED}:JWT:{ACCESS_TOKEN}",
                type=SECURITY,
                token_hash=hash_token_for_logging(new_token.encoded),
            )
            request.state.cookie_manager.set_unsafe_cookie(
                key=MAASLocalCookie.JWT_TOKEN,
                value=new_token.encoded,
            )

            return AuthenticatedUser(
                id=user.id,
                username=user.username,
            )

    async def _get_user_if_valid_token(
        self, request: Request, refresh_token: str
    ) -> User:
        user = await request.state.services.users.get_by_refresh_token(
            refresh_token
        )
        if not user:
            logger.info(
                f"{AUTHN_TOKEN_REUSED}:JWT:{REFRESH_TOKEN}",
                type=SECURITY,
                token_hash=hash_token_for_logging(refresh_token),
            )
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Failed to refresh JWT token - the refresh token is invalid.",
                    )
                ]
            )
        return user

    async def _get_new_jwt(self, request: Request, user: User) -> JWT:
        return await request.state.services.auth.access_token(
            AuthenticatedUser(
                id=user.id,
                username=user.username,
            )
        )

    @classmethod
    def get_issuer(cls):
        return JWT.ISSUER


class OIDCAuthenticationProvider(AuthenticationProvider):
    async def authenticate(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        """
        Returns the authenticated user. Raises an exception if the token is invalid or expired.
        """
        access_token = token
        id_token = request.state.cookie_manager.get_cookie(
            MAASOAuth2Cookie.OAUTH2_ID_TOKEN
        )
        refresh_token = request.state.cookie_manager.get_cookie(
            MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN
        )

        if not id_token or not refresh_token:
            self._clear_oauth_cookies(request)
            logger.info(
                AUTHN_AUTH_FAILED,
                type=SECURITY,
            )
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Missing id_token or refresh_token cookies.",
                    )
                ]
            )

        if not await self._is_token_valid(request, access_token):
            # Try to refresh the access token, if it is no longer valid
            tokens = await self._refresh_access_token(request, refresh_token)

            logger.info(
                f"{AUTHN_TOKEN_CREATED}:OIDC:{ACCESS_TOKEN}",
                type=SECURITY,
                token_hash=hash_token_for_logging(tokens.access_token),
            )

            request.state.cookie_manager.set_auth_cookie(
                value=tokens.access_token,
                key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN,
            )
            # Some providers issue a new refresh token as well.
            if tokens.refresh_token != refresh_token:
                logger.info(
                    f"{AUTHN_TOKEN_CREATED}:OIDC:{REFRESH_TOKEN}",
                    type=SECURITY,
                    token_hash=hash_token_for_logging(tokens.refresh_token),
                )
                request.state.cookie_manager.set_auth_cookie(
                    value=tokens.refresh_token,
                    key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN,
                )

        user: User = (
            await request.state.services.external_oauth.get_user_from_id_token(
                id_token=id_token
            )
        )

        if not user.is_active:
            self._clear_oauth_cookies(request)
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=NOT_AUTHENTICATED_VIOLATION_TYPE,
                        message="Please sign in again to continue.",
                    )
                ]
            )

        return AuthenticatedUser(
            id=user.id,
            username=user.username,
        )

    async def _is_token_valid(self, request: Request, token: str) -> bool:
        try:
            await request.state.services.external_oauth.validate_access_token(
                access_token=token
            )
            return True
        except UnauthorizedException:
            return False

    async def _refresh_access_token(
        self, request: Request, refresh_token: str
    ) -> OAuthRefreshData:
        try:
            return await request.state.services.external_oauth.refresh_access_token(
                refresh_token=refresh_token
            )
        except UnauthorizedException as e:
            logger.info(
                f"{AUTHN_TOKEN_REUSED}:OIDC:{REFRESH_TOKEN}",
                type=SECURITY,
                token_hash=hash_token_for_logging(refresh_token),
            )
            self._clear_oauth_cookies(request)
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Please sign in again to continue.",
                    )
                ]
            ) from e

    def _clear_oauth_cookies(self, request: Request) -> None:
        cookie_manager = request.state.cookie_manager
        for key in (
            MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN,
            MAASOAuth2Cookie.OAUTH2_ID_TOKEN,
            MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN,
        ):
            cookie_manager.clear_cookie(key)


class AuthenticationProvidersCache:
    # All the auth providers will never be None at runtime (see src/maasapiserver/main.py:87)
    # We default them to None to easily use this in tests.
    def __init__(
        self,
        jwt_authentication_providers: Sequence[
            JWTAuthenticationProvider
        ] = None,  # pyright: ignore [reportArgumentType]
        oidc_authentication_provider: OIDCAuthenticationProvider = None,  # pyright: ignore [reportArgumentType]
    ):
        self.jwt_authentication_providers_cache: Dict[
            str, JWTAuthenticationProvider
        ] = (
            {}
            if not jwt_authentication_providers
            else {
                jwt_authentication_provider.get_issuer(): jwt_authentication_provider
                for jwt_authentication_provider in jwt_authentication_providers
            }
        )
        self.oidc_authentication_provider = oidc_authentication_provider

    def get(self, key: str) -> JWTAuthenticationProvider | None:
        return self.jwt_authentication_providers_cache.get(key, None)

    def get_oidc_provider(self) -> OIDCAuthenticationProvider:
        return self.oidc_authentication_provider

    def add(self, provider: JWTAuthenticationProvider) -> None:
        self.jwt_authentication_providers_cache[provider.get_issuer()] = (
            provider
        )

    def size(self) -> int:
        return len(self.jwt_authentication_providers_cache)


class V3AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    If the request targets a v3 endpoint and provides a bearer token we verify the token and add the AuthenticatedUser to
    the request context. Otherwise, we just forward the request to the next middleware.
    """

    def __init__(
        self,
        app: ASGIApp,
        providers_cache: AuthenticationProvidersCache,
    ):
        super().__init__(app)
        self.providers_cache = providers_cache

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Just pass through the request if it's not for a V3 handler. The other V2 endpoints have another authentication
        # architecture/mechanism.
        if not request.url.path.startswith(V3_API_PREFIX):
            return await call_next(request)

        encryptor = await request.state.services.external_oauth.get_encryptor()
        cookie_manager = EncryptedCookieManager(request, encryptor)
        request.state.cookie_manager = cookie_manager

        auth_header = request.headers.get("Authorization", None)
        access_token = cookie_manager.get_cookie(
            MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN
        )

        user = None
        # If no OIDC token or auth_header is specified then the request is unauthenticated and we let the handler
        # decide wether or not to serve it.
        if access_token:
            user = await self._oidc_authentication(request, access_token)
        elif auth_header and auth_header.lower().startswith("bearer "):
            user = await self._jwt_authentication(request, auth_header)

        request.state.authenticated_user = user

        if user is not None:
            logger.info(
                AUTHN_AUTH_SUCCESSFUL,
                type=SECURITY,
                user_id=user.username,
            )

        response = await call_next(request)

        # Bind the response to the cookie manager to set any pending cookies.
        request.state.cookie_manager.bind_response(response)
        return response

    async def _jwt_authentication(
        self, request: Request, auth_header: str
    ) -> AuthenticatedUser:
        token = auth_header.split(" ")[1]
        try:
            header = decode_unverified_jwt(token, check_expiration=False)
        except JWTDecodeError:
            raise BadRequestException(  # noqa: B904
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Could not decode the token.",
                    )
                ]
            )
        issuer = header.get("iss")

        if not issuer or not (provider := self.providers_cache.get(issuer)):
            # TODO: when OIDC providers will be added, check if the issuer is inside the cache. If it's not, retrieve the
            #  configuration from the database, initialize it and add it to the cache. Until that day we just return 400 as the
            #  token comes from an unknown issuer.
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message=f"The authorization token comes from an unknown issuer '{issuer}'",
                    )
                ]
            )

        return await provider.authenticate(request, token)

    async def _oidc_authentication(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        oidc_provider = self.providers_cache.get_oidc_provider()
        return await oidc_provider.authenticate(request, token)
