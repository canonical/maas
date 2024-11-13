import abc
from datetime import timedelta
import json
from typing import Awaitable, Callable, Dict, Sequence

from fastapi import Request, Response
from jose import jwt
from jose.exceptions import JWTError
from macaroonbakery import bakery
import macaroonbakery._utils as utils
from pymacaroons import Macaroon
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from maasapiserver.common.utils.http import extract_absolute_uri
from maasapiserver.v3.constants import V3_API_PREFIX
from maasserver.macaroons import _get_macaroon_caveats_ops
from maasservicelayer.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasservicelayer.auth.jwt import InvalidToken, JWT, UserRole
from maasservicelayer.auth.macaroons.macaroon_client import (
    CandidAsyncClient,
    RbacAsyncClient,
)
from maasservicelayer.auth.macaroons.models.exceptions import (
    MacaroonApiException,
)
from maasservicelayer.auth.macaroons.models.responses import (
    ValidateUserResponse,
)
from maasservicelayer.constants import SYSTEM_USERS
from maasservicelayer.db.repositories.users import (
    UserCreateOrUpdateResourceBuilder,
    UserProfileCreateOrUpdateResourceBuilder,
)
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    DischargeRequiredException,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    USER_EXTERNAL_VALIDATION_FAILED,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.users import User
from maasservicelayer.utils.date import utcnow

EXTERNAL_USER_CHECK_INTERVAL = timedelta(hours=1)


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
        try:
            user = await request.state.services.external_auth.login(
                macaroons=macaroons,
                request_absolute_uri=extract_absolute_uri(request),
            )
        except bakery.DischargeRequiredError as err:
            await self._raise_discharge_exception(
                request, err.cavs(), err.ops()
            )
        except bakery.VerificationError:
            external_auth_info = (
                await request.state.services.external_auth.get_external_auth()
            )
            caveats, ops = _get_macaroon_caveats_ops(
                external_auth_info.url, external_auth_info.domain
            )
            await self._raise_discharge_exception(request, caveats, ops)
        except bakery.PermissionDenied:
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                        message="Missing permissions in the macaroons provided.",
                    )
                ]
            )

        user = await self.validate_user_external_auth(request, user)
        if user is None or user.is_active is False:
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=USER_EXTERNAL_VALIDATION_FAILED,
                        message="External auth user validation failed.",
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

    async def _raise_discharge_exception(self, request, caveats, ops):
        macaroon_bakery = (
            await request.state.services.external_auth.get_bakery(
                extract_absolute_uri(request)
            )
        )
        discharge_macaroon = await request.state.services.external_auth.generate_discharge_macaroon(
            macaroon_bakery=macaroon_bakery,
            caveats=caveats,
            ops=ops,
            req_headers=request.headers,
        )
        raise DischargeRequiredException(macaroon=discharge_macaroon)

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

    async def validate_user_external_auth(
        self,
        request: Request,
        user: User,
        force_check: bool = False,
    ) -> User | None:
        """
        Check if the user is valid through Candid or Rbac.

        Returns:
            User: if the check was successfull
            None: otherwise
        """
        auth_config: ExternalAuthConfig = (
            await request.state.services.external_auth.get_external_auth()
        )
        user_profile = await request.state.services.users.get_user_profile(
            user.username
        )

        now = utcnow()

        if user.username in SYSTEM_USERS:
            # Don't perform the check for system users
            return user
        no_check = (
            user_profile.auth_last_check
            and (user_profile.auth_last_check + EXTERNAL_USER_CHECK_INTERVAL)
            > now
        )
        if no_check and not force_check:
            return user

        try:
            match auth_config.type:
                case ExternalAuthType.CANDID:
                    client = (
                        await request.state.services.external_auth.get_candid_client()
                    )
                    validate_user_response = await self._validate_user_candid(
                        client, auth_config, user.username
                    )

                case ExternalAuthType.RBAC:
                    client = (
                        await request.state.services.external_auth.get_rbac_client()
                    )
                    validate_user_response = await self._validate_user_rbac(
                        client, user.username
                    )
        except MacaroonApiException:
            return None

        user_builder = UserCreateOrUpdateResourceBuilder()
        if validate_user_response.active ^ user.is_active:
            user_builder.with_is_active(validate_user_response.active)
        if validate_user_response.fullname is not None:
            user_builder.with_last_name(validate_user_response.fullname)
        if validate_user_response.email is not None:
            user_builder.with_email(validate_user_response.email)

        user_builder.with_is_superuser(validate_user_response.superuser)
        user = await request.state.services.users.update(
            user.id, user_builder.build()
        )

        profile_builder = UserProfileCreateOrUpdateResourceBuilder()
        profile_builder.with_auth_last_check(now)
        user_profile = await request.state.services.users.update_profile(
            user.id, profile_builder.build()
        )
        return user

    async def _validate_user_candid(
        self,
        client: CandidAsyncClient,
        auth_config: ExternalAuthConfig,
        username: str,
    ) -> ValidateUserResponse:
        try:
            groups_response = await client.get_groups(username)
            user_details = await client.get_user_details(username)
        except MacaroonApiException:
            raise

        if auth_config.admin_group:
            superuser = auth_config.admin_group in groups_response.groups
        else:
            superuser = True
        return ValidateUserResponse(
            **user_details.dict(), active=True, superuser=superuser
        )

    async def _validate_user_rbac(
        self,
        client: RbacAsyncClient,
        username: str,
    ) -> ValidateUserResponse:
        try:
            superuser = await client.is_user_admin(username)
            pools_response = await client.get_resource_pool_ids(
                username,
                {
                    RbacPermission.VIEW,
                    RbacPermission.VIEW_ALL,
                    RbacPermission.DEPLOY_MACHINES,
                    RbacPermission.ADMIN_MACHINES,
                },
            )
            access_to_pools = any(
                [r.resources or r.access_all for r in pools_response]
            )
            user_details = await client.get_user_details(username)
        except MacaroonApiException:
            raise
        return ValidateUserResponse(
            **user_details.dict(),
            active=(superuser or access_to_pools),
            superuser=superuser,
        )


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
