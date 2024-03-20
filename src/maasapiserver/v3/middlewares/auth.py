import abc
import logging
from typing import Awaitable, Callable, Dict, Sequence

from fastapi import Request, Response
from jose import jwt
from jose.exceptions import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from maasapiserver.common.models.constants import INVALID_TOKEN_VIOLATION_TYPE
from maasapiserver.common.models.exceptions import (
    BadRequestException,
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasapiserver.v3.auth.base import AuthenticatedUser
from maasapiserver.v3.auth.jwt import InvalidToken, JWT
from maasapiserver.v3.constants import V3_API_PREFIX

logger = logging.getLogger()


class AuthenticationProvider(abc.ABC):
    @abc.abstractmethod
    async def authenticate(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        """
        Returns the authenticated user. Raise an exception if the token is not valid, is expired or is invalid.
        """
        pass

    @classmethod
    @abc.abstractmethod
    def get_issuer(cls):
        """
        Returns the issuer of this authentication provider.
        """
        pass


class LocalAuthenticationProvider(AuthenticationProvider):
    async def authenticate(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        try:
            jwt_token = (
                await request.state.services.auth.decode_and_verify_token(
                    token
                )
            )
        except InvalidToken:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="The token is not valid.",
                    )
                ]
            )
        return AuthenticatedUser(
            username=jwt_token.subject, roles=jwt_token.roles
        )

    @classmethod
    def get_issuer(cls):
        return JWT.ISSUER


class AuthenticationProvidersCache:
    def __init__(
        self, authentication_providers: Sequence[AuthenticationProvider] = None
    ):
        self.cache: Dict[str, AuthenticationProvider] = (
            {}
            if not authentication_providers
            else {
                authentication_provider.get_issuer(): authentication_provider
                for authentication_provider in authentication_providers
            }
        )

    def get(self, key: str) -> AuthenticationProvider | None:
        return self.cache.get(key, None)

    def add(self, authentication_provider: AuthenticationProvider) -> None:
        self.cache[
            authentication_provider.get_issuer()
        ] = authentication_provider

    def size(self) -> int:
        return len(self.cache)


class V3AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    If the request targets a v3 endpoint and provides a bearer token we verify the token and add the AuthenticatedUser to
    the request context. Otherwise, we just forward the request to the next middleware.
    """

    def __init__(
        self,
        app: ASGIApp,
        providers_cache: AuthenticationProvidersCache = AuthenticationProvidersCache(),
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

        auth_header = request.headers.get("Authorization", None)
        if not auth_header or not auth_header.lower().startswith("bearer "):
            request.state.authenticated_user = None
            return await call_next(request)

        token = auth_header.split(" ")[1]
        try:
            header = jwt.get_unverified_claims(token)
        except JWTError:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Could not decode the token.",
                    )
                ]
            )
        issuer = header.get("iss")
        provider = self.providers_cache.get(issuer)

        if not provider:
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

        request.state.authenticated_user = await provider.authenticate(
            request, token
        )
        return await call_next(request)
