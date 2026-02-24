#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

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
import structlog

from maasapiserver.common.utils.http import extract_absolute_uri
from maasapiserver.v3.auth.cookie_manager import (
    EncryptedCookieManager,
    MAASLocalCookie,
    MAASOAuth2Cookie,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.logging.security import (
    ADMIN,
    AUTHN_AUTH_FAILED,
    AUTHN_AUTH_SUCCESSFUL,
    SECURITY,
    USER,
)
from maasserver.macaroons import _get_macaroon_caveats_ops
from maasservicelayer.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasservicelayer.auth.external_oauth import OAuthRefreshData
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
from maasservicelayer.builders.users import UserBuilder, UserProfileBuilder
from maasservicelayer.constants import SYSTEM_USERS
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


class JWTAuthenticationProvider(AuthenticationProvider):
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
                roles=set(jwt_token.roles),
            )
        except InvalidToken:
            # Use refresh token to get a new JWT if the JWT is expired.
            if not refresh_token:
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
            request.state.cookie_manager.set_unsafe_cookie(
                key=MAASLocalCookie.JWT_TOKEN,
                value=new_token.encoded,
            )

            return AuthenticatedUser(
                id=user.id,
                username=user.username,
                roles=(
                    {UserRole.ADMIN, UserRole.USER}
                    if user.is_superuser
                    else {UserRole.USER}
                ),
            )

    async def _get_user_if_valid_token(
        self, request: Request, refresh_token: str
    ) -> User:
        user = await request.state.services.users.get_by_refresh_token(
            refresh_token
        )
        if not user:
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
                roles=(
                    {UserRole.ADMIN, UserRole.USER}
                    if user.is_superuser
                    else {UserRole.USER}
                ),
            )
        )

    @classmethod
    def get_issuer(cls):
        return JWT.ISSUER


class MacaroonAuthenticationProvider:
    async def authenticate(
        self, request: Request, macaroons: list[list[Macaroon]]
    ) -> AuthenticatedUser:
        """
        Returns the authenticated user. Raises an exception if the macaroon is invalid or expired.
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
            raise ForbiddenException(  # noqa: B904
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
            id=user.id,
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

        validate_user_response = None

        try:
            match auth_config.type:
                case ExternalAuthType.CANDID:
                    client = await request.state.services.external_auth.get_candid_client()
                    validate_user_response = await self._validate_user_candid(
                        client, auth_config, user.username
                    )

                case ExternalAuthType.RBAC:
                    client = await request.state.services.external_auth.get_rbac_client()
                    validate_user_response = await self._validate_user_rbac(
                        client, user.username
                    )
        except MacaroonApiException:
            return None

        # pyright doesn't understand that this variable is always bound
        assert validate_user_response is not None

        user_builder = UserBuilder()
        if validate_user_response.active ^ user.is_active:
            user_builder.is_active = validate_user_response.active
        if validate_user_response.fullname is not None:
            user_builder.last_name = validate_user_response.fullname
        if validate_user_response.email is not None:
            user_builder.email = validate_user_response.email

        user_builder.is_superuser = validate_user_response.superuser
        user = await request.state.services.users.update_by_id(
            user.id, user_builder
        )

        profile_builder = UserProfileBuilder()
        profile_builder.auth_last_check = now
        await request.state.services.users.update_profile(
            user.id, profile_builder
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
            request.state.cookie_manager.set_auth_cookie(
                value=tokens.access_token,
                key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN,
            )
            # Some providers issue a new refresh token as well.
            if tokens.refresh_token != refresh_token:
                request.state.cookie_manager.set_auth_cookie(
                    value=tokens.refresh_token,
                    key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN,
                )

        user: User = (
            await request.state.services.external_oauth.get_user_from_id_token(
                id_token=id_token
            )
        )

        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            roles=(
                {UserRole.ADMIN, UserRole.USER}
                if user.is_superuser
                else {UserRole.USER}
            ),
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
    # All the 3 auth provider will never be None at runtime (see src/maasapiserver/main.py:87)
    # We default them to None to easily use this in tests.
    def __init__(
        self,
        jwt_authentication_providers: Sequence[
            JWTAuthenticationProvider
        ] = None,  # pyright: ignore [reportArgumentType]
        macaroon_authentication_provider: MacaroonAuthenticationProvider = None,  # pyright: ignore [reportArgumentType]
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
        self.macaroon_authentication_provider = (
            macaroon_authentication_provider
        )
        self.oidc_authentication_provider = oidc_authentication_provider

    def get(self, key: str) -> JWTAuthenticationProvider | None:
        return self.jwt_authentication_providers_cache.get(key, None)

    def get_macaroon_provider(self) -> MacaroonAuthenticationProvider:
        return self.macaroon_authentication_provider

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
        # If no OIDC token, auth_header or macaroon is specified then the request is unauthenticated and we let the handler
        # decide wether or not to serve it.
        if access_token:
            user = await self._oidc_authentication(request, access_token)
        elif auth_header and auth_header.lower().startswith("bearer "):
            user = await self._jwt_authentication(request, auth_header)
        elif (
            macaroons
            := self.providers_cache.get_macaroon_provider().extract_macaroons(
                request
            )
        ):
            user = await self._macaroon_authentication(request, macaroons)

        request.state.authenticated_user = user

        if user is not None:
            logger.info(
                AUTHN_AUTH_SUCCESSFUL,
                type=SECURITY,
                userID=user.username,
                role=ADMIN if user.is_admin() else USER,
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
            header = jwt.get_unverified_claims(token)
        except JWTError:
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

    async def _macaroon_authentication(
        self, request: Request, macaroons: list[list[Macaroon]]
    ) -> AuthenticatedUser:
        macaroon_provider = self.providers_cache.get_macaroon_provider()
        return await macaroon_provider.authenticate(request, macaroons)

    async def _oidc_authentication(
        self, request: Request, token: str
    ) -> AuthenticatedUser:
        oidc_provider = self.providers_cache.get_oidc_provider()
        return await oidc_provider.authenticate(request, token)
