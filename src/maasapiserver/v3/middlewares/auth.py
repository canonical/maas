import abc
import json
import logging
from typing import Awaitable, Callable, Dict, Sequence

from fastapi import Request, Response
from jose import jwt
from jose.exceptions import JWTError
import macaroonbakery._utils as utils
from pymacaroons import Macaroon
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from maasapiserver.common.models.constants import INVALID_TOKEN_VIOLATION_TYPE
from maasapiserver.common.models.exceptions import (
    BadRequestException,
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasapiserver.common.utils.http import extract_absolute_uri
from maasapiserver.v3.auth.jwt import InvalidToken, JWT, UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.auth import AuthenticatedUser

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


class DjangoSessionAuthenticationProvider(AuthenticationProvider):
    async def authenticate(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        user = await request.state.services.users.get_by_session_id(token)
        if not user:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="The sessionid is not valid.",
                    )
                ]
            )
        return AuthenticatedUser(
            username=user.username,
            roles=(
                {UserRole.ADMIN, UserRole.USER}
                if user.is_superuser
                else {UserRole.USER}
            ),
        )


class JWTAuthenticationProvider(AuthenticationProvider):
    @classmethod
    @abc.abstractmethod
    def get_issuer(cls):
        """
        Returns the issuer of this authentication provider.
        """
        pass


class LocalAuthenticationProvider(JWTAuthenticationProvider):
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


class MacaroonAuthenticationProvider:
    async def authenticate(
        self, request: Request, macaroons: list[list[Macaroon]]
    ) -> AuthenticatedUser:
        """
        Returns the authenticated user. Raise an exception if the macaroon is not valid, is expired or is invalid.
        """
        user = await request.state.services.external_auth.login(
            macaroons=macaroons,
            request_absolute_uri=extract_absolute_uri(request),
        )
        return AuthenticatedUser(
            username=user.username,
            # TODO: MAASENG-3539 we have to use the Candid/RBAC client to fetch the groups of the user and set the roles
            #  accordingly here. For the time being, we consider everybody as a simple user.
            roles={UserRole.USER},
        )

    def extract_macaroons(self, request: Request) -> list[list[Macaroon]]:
        def decode_macaroon(data) -> list[Macaroon] | None:
            try:
                data = utils.b64decode(data)
                data_as_objs = json.loads(data.decode("utf-8"))
            except ValueError:
                return
            return [utils.macaroon_from_dict(x) for x in data_as_objs]

        mss = []
        for cookie, value in request.cookies.items():
            if cookie.lower().startswith("macaroon-"):
                mss.append(decode_macaroon(value))

        macaroon_header = request.headers.get("Macaroons", None)
        if macaroon_header:
            for h in macaroon_header.split(","):
                mss.append(decode_macaroon(h))
        return mss


class AuthenticationProvidersCache:
    def __init__(
        self,
        jwt_authentication_providers: Sequence[
            JWTAuthenticationProvider
        ] = None,
        session_authentication_provider: AuthenticationProvider = None,
        macaroon_authentication_provider: MacaroonAuthenticationProvider = None,
    ):
        self.jwt_authentication_providers_cache: Dict[
            str, AuthenticationProvider
        ] = (
            {}
            if not jwt_authentication_providers
            else {
                jwt_authentication_provider.get_issuer(): jwt_authentication_provider
                for jwt_authentication_provider in jwt_authentication_providers
            }
        )
        self.session_authentication_provider = session_authentication_provider
        self.macaroon_authentication_provider = (
            macaroon_authentication_provider
        )

    def get(self, key: str) -> JWTAuthenticationProvider | None:
        return self.jwt_authentication_providers_cache.get(key, None)

    def get_session_provider(self) -> AuthenticationProvider | None:
        return self.session_authentication_provider

    def get_macaroon_provider(self) -> MacaroonAuthenticationProvider | None:
        return self.macaroon_authentication_provider

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
        sessionid = request.cookies.get("sessionid", None)

        user = None
        # TODO: once the UI moves to the new authentication mechanism, we should drop the support for the django session here.
        #  This is not supposed to be part of the current v3 api contract
        #
        # If no sessionid nor auth_header nor macaroon is specified then the request is unauthenticated and we let the handler
        # decide wether or not to serve it.
        if sessionid:
            user = await self._session_authentication(request, sessionid)
        elif auth_header and auth_header.lower().startswith("bearer "):
            user = await self._jwt_authentication(request, auth_header)
        elif macaroons := self.providers_cache.get_macaroon_provider().extract_macaroons(
            request
        ):
            user = await self._macaroon_authentication(request, macaroons)
        request.state.authenticated_user = user

        return await call_next(request)

    async def _session_authentication(
        self, request: Request, sessionid: str
    ) -> AuthenticatedUser:
        session_provider = self.providers_cache.get_session_provider()
        return await session_provider.authenticate(request, sessionid)

    async def _jwt_authentication(
        self, request: Request, auth_header: str
    ) -> AuthenticatedUser:
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

        return await provider.authenticate(request, token)

    async def _macaroon_authentication(
        self, request: Request, macaroons: list[list[Macaroon]]
    ) -> AuthenticatedUser:
        macaroon_provider = self.providers_cache.get_macaroon_provider()
        return await macaroon_provider.authenticate(request, macaroons)
