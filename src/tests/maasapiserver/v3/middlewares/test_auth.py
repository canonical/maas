from datetime import datetime
from typing import Any, AsyncIterator, Iterator
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI, Request
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.responses import Response

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.common.db import Database
from maasapiserver.common.middlewares.exceptions import ExceptionMiddleware
from maasapiserver.common.models.exceptions import UnauthorizedException
from maasapiserver.v2.constants import V2_API_PREFIX
from maasapiserver.v3.api.models.responses.oauth2 import AccessTokenResponse
from maasapiserver.v3.auth.base import AuthenticatedUser
from maasapiserver.v3.auth.jwt import InvalidToken, JWT, UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.middlewares.auth import (
    AuthenticationProvidersCache,
    DjangoSessionAuthenticationProvider,
    LocalAuthenticationProvider,
    V3AuthenticationMiddleware,
)
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maasapiserver.v3.models.users import User
from tests.fixtures.factories.user import create_test_session, create_test_user
from tests.maasapiserver.fixtures.db import Fixture


@pytest.fixture
def auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()

    app.add_middleware(
        V3AuthenticationMiddleware,
        providers_cache=AuthenticationProvidersCache(
            jwt_authentication_providers=[LocalAuthenticationProvider()],
            session_authentication_provider=DjangoSessionAuthenticationProvider(),
        ),
    )
    app.add_middleware(ServicesMiddleware)
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ExceptionMiddleware)

    @app.get("/MAAS/a/v3/users/{username}/token")
    async def get_token(
        request: Request, username: str
    ) -> AccessTokenResponse:
        jwt_key = (
            await request.state.services.auth._get_or_create_cached_jwt_key()
        )
        return AccessTokenResponse(
            token_type="bearer",
            access_token=JWT.create(
                jwt_key, username, [UserRole.USER]
            ).encoded,
        )

    @app.get("/MAAS/a/v3/users/{username}/invalid_token")
    async def get_invalid_token(
        request: Request, username: str
    ) -> AccessTokenResponse:
        return AccessTokenResponse(
            token_type="bearer",
            access_token=JWT.create(
                "definitely_not_the_key", username, [UserRole.USER]
            ).encoded,
        )

    @app.get("/MAAS/a/v3/users/me")
    async def get_me(request: Request) -> Any:
        # V3 endpoints have authenticated_user == None if no bearer tokens was provided
        if request.state.authenticated_user:
            return AuthenticatedUser(
                username=request.state.authenticated_user.username,
                roles=request.state.authenticated_user.roles,
            )
        return Response(content="authenticated_user is None", status_code=401)

    @app.get(V2_API_PREFIX)
    async def get_v2(request: Request) -> Response:
        # Other endpoints should not have authenticated_user at all.
        if hasattr(request.state, "authenticated_user"):
            return Response(status_code=500)
        return Response(status_code=200)

    yield app


@pytest.fixture
async def auth_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=auth_app, base_url="http://test") as client:
        yield client


class TestV3AuthenticationMiddleware:
    async def test_authenticated_user(self, auth_client: AsyncClient) -> None:
        # v2 endpoints should not have the authenticated_user in the request context
        v2_response = await auth_client.get(V2_API_PREFIX)
        assert v2_response.status_code == 200

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
        invalid_token = AccessTokenResponse(**invalid_token_response.json())
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
        token_response = AccessTokenResponse(**token_response.json())
        authenticated_v3_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Authorization": "bearer " + token_response.access_token},
        )
        assert authenticated_v3_response.status_code == 200
        authenticated_user = AuthenticatedUser(
            **authenticated_v3_response.json()
        )
        assert authenticated_user.username == "test"
        assert authenticated_user.roles == {UserRole.USER}

    async def test_authentication_with_sessionid(
        self, fixture: Fixture, auth_client: AsyncClient
    ) -> None:
        # invalid session_id
        invalid_token_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Cookie": "sessionid=invalid"},
        )
        assert invalid_token_response.status_code == 401

        # valid user session_id
        user = await create_test_user(fixture)
        session_id = "mysession"
        await create_test_session(
            fixture=fixture, user_id=user.id, session_id=session_id
        )
        authenticated_v3_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Cookie": f"sessionid={session_id}"},
        )
        assert authenticated_v3_response.status_code == 200
        authenticated_user = AuthenticatedUser(
            **authenticated_v3_response.json()
        )
        assert authenticated_user.username == "myusername"
        assert authenticated_user.roles == {UserRole.USER}

        # valid admin session_id
        admin = await create_test_user(
            fixture, username="admin", is_superuser=True
        )
        admin_session_id = "adminsession"
        await create_test_session(
            fixture=fixture, user_id=admin.id, session_id=admin_session_id
        )
        authenticated_v3_response = await auth_client.get(
            f"{V3_API_PREFIX}/users/me",
            headers={"Cookie": f"sessionid={admin_session_id}"},
        )
        assert authenticated_v3_response.status_code == 200
        authenticated_admin = AuthenticatedUser(
            **authenticated_v3_response.json()
        )
        assert authenticated_admin.username == "admin"
        assert authenticated_admin.roles == {UserRole.ADMIN, UserRole.USER}


class TestAuthenticationProvidersCache:
    def test_constructor(self) -> None:
        cache = AuthenticationProvidersCache()
        assert cache.size() == 0
        assert cache.get_session_provider() is None

        session_provider = DjangoSessionAuthenticationProvider()
        cache = AuthenticationProvidersCache(
            jwt_authentication_providers=[LocalAuthenticationProvider()],
            session_authentication_provider=session_provider,
        )
        assert cache.size() == 1
        assert cache.get(LocalAuthenticationProvider.get_issuer()) is not None
        assert cache.get_session_provider() is session_provider

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


class TestDjangoSessionAuthenticationProvider:
    def _make_user(self, is_superuser: bool = False) -> User:
        return User(
            id=0,
            username="test",
            password="password",
            is_superuser=is_superuser,
            first_name="name",
            last_name="last_name",
            is_staff=False,
            is_active=True,
            date_joined=datetime.utcnow(),
        )

    async def test_dispatch(self) -> None:
        sessionid = "test"

        user = self._make_user()
        request = Mock(Request)
        request.state.services.users.get_by_session_id = AsyncMock(
            return_value=user
        )

        provider = DjangoSessionAuthenticationProvider()
        authenticated_user = await provider.authenticate(request, sessionid)

        assert authenticated_user.username == user.username
        assert authenticated_user.roles == {UserRole.USER}

    async def test_dispatch_admin(self) -> None:
        sessionid = "test"

        user = self._make_user(is_superuser=True)
        request = Mock(Request)
        request.state.services.users.get_by_session_id = AsyncMock(
            return_value=user
        )

        provider = DjangoSessionAuthenticationProvider()
        authenticated_user = await provider.authenticate(request, sessionid)

        assert authenticated_user.username == user.username
        assert authenticated_user.roles == {UserRole.ADMIN, UserRole.USER}

    async def test_dispatch_unauthenticated(self) -> None:
        request = Mock(Request)
        request.state.services.users.get_by_session_id = AsyncMock(
            return_value=None
        )

        provider = DjangoSessionAuthenticationProvider()
        with pytest.raises(UnauthorizedException):
            await provider.authenticate(request, "")


class TestLocalAuthenticationProvider:
    async def test_dispatch(self) -> None:
        jwt = JWT.create("123", "test", [UserRole.USER])
        request = Mock(Request)
        request.state.services.auth.decode_and_verify_token = AsyncMock(
            return_value=jwt
        )

        provider = LocalAuthenticationProvider()
        user = await provider.authenticate(request, jwt.encoded)

        assert user.username == "test"
        assert user.roles == {UserRole.USER}

    async def test_dispatch_unauthenticated(self) -> None:
        request = Mock(Request)
        request.state.services.auth.decode_and_verify_token = AsyncMock(
            side_effect=InvalidToken()
        )

        provider = LocalAuthenticationProvider()
        with pytest.raises(UnauthorizedException):
            await provider.authenticate(request, "")
