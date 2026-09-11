# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, AsyncIterator, Callable, Iterator
from unittest.mock import AsyncMock, call, Mock

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.responses import Response

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.common.middlewares.exceptions import ExceptionMiddleware
from maasapiserver.v3.api.public.models.responses.oauth2 import TokenResponse
from maasapiserver.v3.auth.cookie_manager import (
    EncryptedCookieManager,
    MAASLocalCookie,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.middlewares.auth import (
    AuthenticationProvidersCache,
    LocalAuthenticationProvider,
    OIDCAuthenticationProvider,
    V3AuthenticationMiddleware,
)
from maasapiserver.v3.middlewares.context import ContextMiddleware
from maasapiserver.v3.middlewares.services import ServicesMiddleware
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
from maasservicelayer.auth.external_oauth import OAuthRefreshData
from maasservicelayer.auth.jwt import InvalidToken, JWT
from maasservicelayer.db import Database
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    NOT_AUTHENTICATED_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.users import User
from maasservicelayer.services import CacheForServices
from maasservicelayer.services.auth import AuthService
from maasservicelayer.services.external_auth import ExternalOAuthService
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture


def _make_user(is_superuser: bool = False) -> User:
    return User(
        id=0,
        username="test",
        password="password",
        is_superuser=is_superuser,
        first_name="name",
        last_name="last_name",
        is_staff=False,
        is_active=True,
        date_joined=utcnow(),
    )


def _make_oidc_user(is_superuser: bool = False) -> User:
    return User(
        id=0,
        username="user@example.com",
        email="user@example.com",
        password="password",
        is_superuser=is_superuser,
        first_name="oidc_name",
        last_name="oidc_last_name",
        is_staff=False,
        is_active=True,
        date_joined=utcnow(),
    )


@pytest.fixture
def auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()
    services_cache = CacheForServices()

    app.add_middleware(
        V3AuthenticationMiddleware,
        providers_cache=AuthenticationProvidersCache(
            jwt_authentication_providers=[LocalAuthenticationProvider()],
            oidc_authentication_provider=OIDCAuthenticationProvider(),
        ),
    )
    app.add_middleware(ServicesMiddleware, cache=services_cache)
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ExceptionMiddleware)
    app.add_middleware(ContextMiddleware)
    app.add_event_handler("shutdown", services_cache.close)

    @app.get("/MAAS/a/v3/users/{username}/token")
    async def get_token(request: Request, username: str) -> TokenResponse:
        jwt_key = (
            await request.state.services.auth._get_or_create_cached_jwt_key()
        )
        return TokenResponse(
            token_type="bearer",
            access_token=JWT.create(jwt_key, username, 0).encoded,
        )

    @app.get("/MAAS/a/v3/users/{username}/invalid_token")
    async def get_invalid_token(
        request: Request, username: str
    ) -> TokenResponse:
        return TokenResponse(
            token_type="bearer",
            access_token=JWT.create(
                "definitely_not_the_key", username, 0
            ).encoded,
        )

    @app.get("/MAAS/a/v3/users/me")
    async def get_me(request: Request) -> Any:
        # V3 endpoints have authenticated_user == None if no bearer tokens was provided
        if request.state.authenticated_user:
            return AuthenticatedUser(
                id=request.state.authenticated_user.id,
                username=request.state.authenticated_user.username,
            )
        return Response(content="authenticated_user is None", status_code=401)

    yield app


@pytest.fixture
async def auth_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as client:
        yield client


class TestV3AuthenticationMiddleware:
    async def test_authenticated_user(self, auth_client: AsyncClient) -> None:
        # v3 endpoints should have the authenticated_user in the request context if the request was not authenticated
        v3_response = await auth_client.get(f"{V3_API_PREFIX}/users/me")
        assert v3_response.text == "authenticated_user is None"
        assert v3_response.status_code == 401

        # v3 requests with malformed bearer tokens should 400
        v3_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Authorization": "bearer xyz"},
        )
        assert v3_response.status_code == 400
        error_response = ErrorBodyResponse(**v3_response.json())
        assert error_response.kind == "Error"

        # v3 requests with invalid bearer tokens should 401
        invalid_token_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/test/invalid_token"
        )
        invalid_token = TokenResponse(**invalid_token_response.json())
        invalid_token_v3_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Authorization": "bearer " + invalid_token.access_token},
        )
        assert invalid_token_v3_response.status_code == 401
        error_response = ErrorBodyResponse(**invalid_token_v3_response.json())
        assert error_response.kind == "Error"

        # valid token
        token_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/test/token"
        )
        token_response = TokenResponse(**token_response.json())
        authenticated_v3_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Authorization": "bearer " + token_response.access_token},
        )
        assert authenticated_v3_response.status_code == 200
        authenticated_user = AuthenticatedUser(
            **authenticated_v3_response.json()
        )
        assert authenticated_user.username == "test"

    async def test_authentication_creates_logging_context(
        self,
        fixture: Fixture,
        mocker: MockerFixture,
    ) -> None:
        mock_logger = mocker.patch("maasapiserver.v3.middlewares.auth.logger")
        request_mock = Mock(Request)
        request_mock.cookies = {}
        request_mock.state.services.external_oauth.get_encryptor = AsyncMock(
            return_value=None
        )
        authenticated_user = AuthenticatedUser(id=0, username="myuser")
        authenticated_admin = AuthenticatedUser(id=1, username="admin")
        local_auth_provider_mock = Mock(LocalAuthenticationProvider)
        authentication_providers_cache = AuthenticationProvidersCache(
            jwt_authentication_providers=[local_auth_provider_mock],
            oidc_authentication_provider=None,
        )
        auth_middleware = V3AuthenticationMiddleware(
            app=None, providers_cache=authentication_providers_cache
        )
        auth_middleware._jwt_authentication = AsyncMock(
            side_effect=[
                BadRequestException(),
                authenticated_user,
                authenticated_admin,
            ]
        )

        # invalid JWT token
        request_mock.headers = {"Authorization": "bearer invalid_token"}

        with pytest.raises(BadRequestException):
            await auth_middleware.dispatch(request_mock, AsyncMock(Callable))
        mock_logger.assert_not_called()

        # valid user JWT Token
        user = await create_test_user(
            fixture, username="myuser", is_superuser=False
        )
        valid_token = JWT.create("123", user.username, user.id)
        request_mock.headers = {
            "Authorization": "bearer " + valid_token.encoded
        }
        await auth_middleware.dispatch(request_mock, AsyncMock(Callable))
        mock_logger.info.assert_called_with(
            AUTHN_AUTH_SUCCESSFUL, type=SECURITY, user_id="myuser"
        )

        # valid admin JWT Token
        admin = await create_test_user(
            fixture, username="admin", is_superuser=True
        )
        valid_admin_token = JWT.create("123", admin.username, admin.id)
        request_mock.headers = {
            "Authorization": "bearer " + valid_admin_token.encoded
        }
        await auth_middleware.dispatch(request_mock, AsyncMock(Callable))
        mock_logger.info.assert_called_with(
            AUTHN_AUTH_SUCCESSFUL, type=SECURITY, user_id="admin"
        )

    async def test_authentication_with_oidc(
        self, fixture: Fixture, mocker
    ) -> None:
        oidc_user = await create_test_user(
            fixture,
            username="user@example.com",
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            is_superuser=False,
        )
        oidc_auth_provider_mock = Mock(OIDCAuthenticationProvider)
        authenticated_user = AuthenticatedUser(
            id=oidc_user.id,
            username=oidc_user.username,
        )
        oidc_auth_provider_mock.authenticate.return_value = authenticated_user
        authentication_providers_cache = AuthenticationProvidersCache(
            jwt_authentication_providers=None,
            oidc_authentication_provider=oidc_auth_provider_mock,
        )
        auth_middleware = V3AuthenticationMiddleware(
            app=None, providers_cache=authentication_providers_cache
        )
        request_mock = Mock(Request)
        request_mock.headers = {}
        request_mock.cookies = {}
        cookie_manager = Mock(EncryptedCookieManager)
        request_mock.state.services.external_oauth.get_encryptor = AsyncMock(
            return_value=Mock()
        )
        mocker.patch(
            "maasapiserver.v3.middlewares.auth.EncryptedCookieManager",
            return_value=cookie_manager,
        )
        cookie_manager.get_cookie.return_value = "oidc_access_token_value"
        call_next_mock = AsyncMock(Callable)
        await auth_middleware.dispatch(request_mock, call_next_mock)
        assert request_mock.state.authenticated_user == authenticated_user
        call_next_mock.assert_called_once_with(request_mock)
        oidc_auth_provider_mock.authenticate.assert_called_once_with(
            request_mock, "oidc_access_token_value"
        )


class TestAuthenticationProvidersCache:
    def test_constructor(self) -> None:
        cache = AuthenticationProvidersCache()
        assert cache.size() == 0

        oidc_authentication_provider = OIDCAuthenticationProvider()
        cache = AuthenticationProvidersCache(
            jwt_authentication_providers=[LocalAuthenticationProvider()],
            oidc_authentication_provider=oidc_authentication_provider,
        )
        assert cache.size() == 1
        assert cache.get(LocalAuthenticationProvider.get_issuer()) is not None
        assert cache.get_oidc_provider() is oidc_authentication_provider

    def test_get(self):
        provider = LocalAuthenticationProvider()
        cache = AuthenticationProvidersCache([provider])
        assert cache.size() == 1
        assert id(provider) == id(
            cache.get(LocalAuthenticationProvider.get_issuer())
        )

    def test_add(self):
        provider = LocalAuthenticationProvider()
        cache = AuthenticationProvidersCache()
        cache.add(provider)
        assert cache.size() == 1
        assert id(provider) == id(
            cache.get(LocalAuthenticationProvider.get_issuer())
        )

        replacement = LocalAuthenticationProvider()
        cache.add(replacement)
        assert cache.size() == 1
        assert id(replacement) == id(
            cache.get(LocalAuthenticationProvider.get_issuer())
        )


class TestLocalAuthenticationProvider:
    async def test_dispatch(self) -> None:
        jwt = JWT.create("123", "test", 0)
        request = Mock(Request)
        request.state.services.auth = Mock(AuthService)
        request.state.services.auth.decode_and_verify_token.return_value = jwt

        provider = LocalAuthenticationProvider()
        user = await provider.authenticate(request, jwt.encoded)

        assert user.username == "test"
        assert user.id == 0

    async def test_dispatch_unauthenticated_with_no_refresh_token(
        self,
    ) -> None:
        request = Mock(Request)
        request.state.cookie_manager = Mock(EncryptedCookieManager)
        request.state.cookie_manager.get_unsafe_cookie.return_value = None
        request.state.services.auth = Mock(AuthService)
        request.state.services.auth.decode_and_verify_token.side_effect = (
            InvalidToken()
        )

        provider = LocalAuthenticationProvider()
        with pytest.raises(UnauthorizedException) as exc_info:
            await provider.authenticate(request, "")
        details = exc_info.value.details
        assert details is not None
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
        assert (
            details[0].message
            == "The token is not valid, and no refresh token is present."
        )

    async def test_dispatch_refreshes_token(self) -> None:
        request = Mock(Request)
        user = _make_user()
        token = JWT.create("123", user.username, user.id)
        request.state.services.auth = Mock(AuthService)
        request.state.services.Users = Mock(UsersService)
        request.state.cookie_manager = Mock(EncryptedCookieManager)
        request.state.cookie_manager.get_unsafe_cookie.return_value = (
            "refresh_token_value"
        )
        request.state.services.auth.decode_and_verify_token.side_effect = (
            InvalidToken()
        )
        request.state.services.users.get_by_refresh_token = AsyncMock(
            return_value=user
        )
        request.state.services.auth.access_token.return_value = token

        provider = LocalAuthenticationProvider()
        authenticated_user = await provider.authenticate(
            request, "invalid_token"
        )

        assert authenticated_user.username == user.username
        assert authenticated_user.id == user.id
        request.state.cookie_manager.set_unsafe_cookie.assert_called_once_with(
            key=MAASLocalCookie.JWT_TOKEN,
            value=token.encoded,
        )

    async def test_dispatch_fails_to_refresh_token(self) -> None:
        request = Mock(Request)
        request.state.services.auth = Mock(AuthService)
        request.state.services.Users = Mock(UsersService)
        request.state.cookie_manager = Mock(EncryptedCookieManager)
        request.state.cookie_manager.get_unsafe_cookie.return_value = (
            "refresh_token_value"
        )
        request.state.services.auth.decode_and_verify_token.side_effect = (
            InvalidToken()
        )
        request.state.services.users.get_by_refresh_token = AsyncMock(
            return_value=None
        )

        provider = LocalAuthenticationProvider()
        with pytest.raises(UnauthorizedException) as exc_info:
            await provider.authenticate(request, "invalid_token")
        details = exc_info.value.details
        assert details is not None
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
        assert (
            details[0].message
            == "Failed to refresh JWT token - the refresh token is invalid."
        )

    async def test_jwt_token_reuse_logging(
        self, mocker: MockerFixture
    ) -> None:
        """Test that JWT token reuse attempts are logged with token hash."""
        mock_logger = mocker.patch("maasapiserver.v3.middlewares.auth.logger")
        request = Mock(Request)
        request.state.cookie_manager = Mock(EncryptedCookieManager)
        request.state.cookie_manager.get_unsafe_cookie.return_value = None
        request.state.services.auth = Mock(AuthService)
        request.state.services.auth.decode_and_verify_token.side_effect = (
            InvalidToken()
        )

        provider = LocalAuthenticationProvider()
        test_token = "test_invalid_token"
        with pytest.raises(UnauthorizedException):
            await provider.authenticate(request, test_token)

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_REUSED}:JWT:{ACCESS_TOKEN}",
            type=SECURITY,
            token_hash=hash_token_for_logging(test_token),
        )


class TestOIDCAuthenticationProvider:
    def mock_request(self) -> Mock:
        request = Mock(Request)
        request.state.services.external_oauth = Mock(ExternalOAuthService)
        request.state.cookie_manager = Mock(EncryptedCookieManager)
        request.state.cookie_manager.get_cookie = Mock()
        request.state.cookie_manager.get_cookie.side_effect = [
            "idtoken",
            "refreshtoken",
        ]
        request.state.cookie_manager.set_auth_cookie = Mock()
        return request

    async def test_dispatch_with_valid_token(self) -> None:
        user = _make_oidc_user()
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=True)
        provider._refresh_access_token = AsyncMock()

        authenticated_user = await provider.authenticate(
            request, "accesstoken"
        )

        provider._is_token_valid.assert_awaited_once_with(
            request, "accesstoken"
        )
        provider._refresh_access_token.assert_not_awaited()
        assert authenticated_user.username == "user@example.com"
        request.state.cookie_manager.set_auth_cookie.assert_not_called()

    async def test_dispatch_refreshes_token_with_new_refresh_token(
        self,
    ) -> None:
        user = _make_oidc_user()
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=False)
        provider._refresh_access_token = AsyncMock(
            return_value=OAuthRefreshData("newaccesstoken", "newrefreshtoken")
        )

        authenticated_user = await provider.authenticate(
            request, "accesstoken"
        )

        assert authenticated_user.username == "user@example.com"
        provider._is_token_valid.assert_awaited_once_with(
            request, "accesstoken"
        )
        provider._refresh_access_token.assert_awaited_once_with(
            request, "refreshtoken"
        )
        request.state.cookie_manager.set_auth_cookie.assert_any_call(
            value="newaccesstoken", key="maas.oauth2_access_token_cookie"
        )
        request.state.cookie_manager.set_auth_cookie.assert_any_call(
            value="newrefreshtoken", key="maas.oauth2_refresh_token_cookie"
        )

    async def test_dispatch_refreshes_token_with_same_refresh_token(
        self,
    ) -> None:
        user = _make_oidc_user()
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=False)
        provider._refresh_access_token = AsyncMock(
            return_value=OAuthRefreshData("newaccesstoken", "refreshtoken")
        )

        authenticated_user = await provider.authenticate(
            request, "accesstoken"
        )

        assert authenticated_user.username == "user@example.com"
        provider._is_token_valid.assert_awaited_once_with(
            request, "accesstoken"
        )
        provider._refresh_access_token.assert_awaited_once_with(
            request, "refreshtoken"
        )
        request.state.cookie_manager.set_auth_cookie.assert_called_once_with(
            value="newaccesstoken", key="maas.oauth2_access_token_cookie"
        )

    async def test_dispatch_fails_to_refresh_token(self) -> None:
        user = _make_oidc_user()
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user
        request.state.services.external_oauth.refresh_access_token.side_effect = UnauthorizedException()

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=False)
        provider._clear_oauth_cookies = Mock()

        with pytest.raises(UnauthorizedException) as exc_info:
            await provider.authenticate(request, "accesstoken")
        details = exc_info.value.details
        assert details is not None
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
        assert details[0].message == "Please sign in again to continue."
        provider._is_token_valid.assert_awaited_once_with(
            request, "accesstoken"
        )
        request.state.cookie_manager.set_auth_cookie.assert_not_called()
        provider._clear_oauth_cookies.assert_called_once_with(request)

    async def test_dispatch_with_missing_cookies(
        self, mocker: MockerFixture
    ) -> None:
        request = self.mock_request()
        request.state.cookie_manager.get_cookie.side_effect = [
            None,
            None,
        ]
        mock_logger = mocker.patch("maasapiserver.v3.middlewares.auth.logger")

        provider = OIDCAuthenticationProvider()
        provider._clear_oauth_cookies = Mock()

        with pytest.raises(BadRequestException) as exc_info:
            await provider.authenticate(request, "accesstoken")
        details = exc_info.value.details
        assert details is not None
        assert (
            details[0].message == "Missing id_token or refresh_token cookies."
        )
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
        mock_logger.info.assert_called_with(AUTHN_AUTH_FAILED, type=SECURITY)
        provider._clear_oauth_cookies.assert_called_once_with(request)

    async def test_oidc_access_token_refresh_logging(
        self, mocker: MockerFixture
    ) -> None:
        """Test that OIDC access token refresh is logged."""
        mock_logger = mocker.patch("maasapiserver.v3.middlewares.auth.logger")
        user = _make_oidc_user()
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=False)
        provider._refresh_access_token = AsyncMock(
            return_value=OAuthRefreshData("newaccesstoken", "refreshtoken")
        )

        await provider.authenticate(request, "accesstoken")

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_CREATED}:OIDC:{ACCESS_TOKEN}",
            type=SECURITY,
            token_hash=hash_token_for_logging("newaccesstoken"),
        )

    async def test_oidc_refresh_token_refresh_logging(
        self, mocker: MockerFixture
    ) -> None:
        """Test that OIDC refresh token refresh is logged when a new one is issued."""
        mock_logger = mocker.patch("maasapiserver.v3.middlewares.auth.logger")
        user = _make_oidc_user()
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=False)
        provider._refresh_access_token = AsyncMock(
            return_value=OAuthRefreshData("newaccesstoken", "newrefreshtoken")
        )

        await provider.authenticate(request, "accesstoken")

        assert mock_logger.info.call_count == 2
        mock_logger.info.assert_has_calls(
            [
                call(
                    f"{AUTHN_TOKEN_CREATED}:OIDC:{ACCESS_TOKEN}",
                    type=SECURITY,
                    token_hash=hash_token_for_logging("newaccesstoken"),
                ),
                call(
                    f"{AUTHN_TOKEN_CREATED}:OIDC:{REFRESH_TOKEN}",
                    type=SECURITY,
                    token_hash=hash_token_for_logging("newrefreshtoken"),
                ),
            ]
        )

    async def test_oidc_refresh_token_reuse_logging(
        self, mocker: MockerFixture
    ) -> None:
        """Test that OIDC refresh token reuse is logged when refresh fails."""
        mock_logger = mocker.patch("maasapiserver.v3.middlewares.auth.logger")
        request = self.mock_request()
        request.state.services.external_oauth.refresh_access_token.side_effect = UnauthorizedException()

        provider = OIDCAuthenticationProvider()
        provider._clear_oauth_cookies = Mock()

        with pytest.raises(UnauthorizedException):
            await provider._refresh_access_token(
                request, "invalidrefreshtoken"
            )

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_REUSED}:OIDC:{REFRESH_TOKEN}",
            type=SECURITY,
            token_hash=hash_token_for_logging("invalidrefreshtoken"),
        )

    async def test_dispatch_inactive_user_raises_forbidden(self) -> None:
        user = _make_oidc_user()
        user.is_active = False
        request = self.mock_request()
        request.state.services.external_oauth.get_user_from_id_token.return_value = user

        provider = OIDCAuthenticationProvider()
        provider._is_token_valid = AsyncMock(return_value=True)
        provider._clear_oauth_cookies = Mock()

        with pytest.raises(ForbiddenException) as exc_info:
            await provider.authenticate(request, "accesstoken")
        details = exc_info.value.details
        assert details is not None
        assert details[0].type == NOT_AUTHENTICATED_VIOLATION_TYPE
        assert details[0].message == "Please sign in again to continue."
        provider._clear_oauth_cookies.assert_called_once_with(request)
