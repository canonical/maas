from json import JSONDecodeError
from typing import AsyncIterator, Awaitable, Callable, Iterator, Optional

from fastapi import Depends, FastAPI
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db import Database
from maasservicelayer.exceptions.catalog import (
    DischargeRequiredException,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.models.auth import AuthenticatedUser


class AuthTestMiddleware(BaseHTTPMiddleware):
    """
    This middleware assumes that every request body is an AuthenticatedUser and set it in the request context. We have to do
    this because the dependency injection mechanism of fastapi is lacking of flexibility and forces us to go through an endpoint
    to test a function that uses `Depends`. See https://github.com/tiangolo/fastapi/discussions/7720 .
    This is a workaround to make the testing of the permiossion functions "easier".
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            body = await request.json()
            request.state.authenticated_user = (
                AuthenticatedUser(**body) if body else None
            )
        except JSONDecodeError:
            request.state.authenticated_user = None
        try:
            return await call_next(request)
        except (UnauthorizedException, DischargeRequiredException):
            return Response(status_code=401)
        except ForbiddenException:
            return Response(status_code=403)


@pytest.fixture
def auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    app = FastAPI()

    app.add_middleware(AuthTestMiddleware)
    app.add_middleware(ServicesMiddleware)
    app.add_middleware(transaction_middleware_class, db=db)

    @app.post(f"{V3_API_PREFIX}/user")
    async def get_user(
        authenticated_user: Optional[AuthenticatedUser] = Depends(
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    @app.post(
        f"{V3_API_PREFIX}/user_permissions",
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def user_with_permissions() -> Response:
        return Response(status_code=200)

    @app.post(
        f"{V3_API_PREFIX}/admin_permissions",
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def admin_with_permissions() -> Response:
        return Response(status_code=200)

    yield app


@pytest.fixture
async def auth_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=auth_app, base_url="http://test/") as client:
        yield client


class TestPermissionsFunctions:
    def _build_request(self, username: str, roles: set[UserRole]) -> str:
        return jsonable_encoder(
            AuthenticatedUser(username=username, roles=roles)
        )

    async def test_get_user(self, auth_client: AsyncClient) -> None:
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.username == "test"
        assert authenticated_user.roles == {UserRole.USER}

        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user_permissions",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 200
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user_permissions"
        )
        assert user_response.status_code == 401
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user_permissions",
            json=self._build_request("test", {UserRole.ADMIN}),
        )
        assert user_response.status_code == 403
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user_permissions",
            json=self._build_request("test", {UserRole.USER, UserRole.ADMIN}),
        )
        assert user_response.status_code == 200

        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/admin_permissions",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 403
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/admin_permissions"
        )
        assert user_response.status_code == 401
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/admin_permissions",
            json=self._build_request("test", {UserRole.ADMIN}),
        )
        assert user_response.status_code == 200
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/admin_permissions",
            json=self._build_request("test", {UserRole.USER, UserRole.ADMIN}),
        )
        assert user_response.status_code == 200
