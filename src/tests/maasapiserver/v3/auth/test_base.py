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
from maasapiserver.v3.middlewares.context import ContextMiddleware
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db import Database
from maasservicelayer.enums.rbac import RbacPermission
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
    app.add_middleware(ContextMiddleware)

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

    @app.post(
        f"{V3_API_PREFIX}/rbac_pools",
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                    rbac_permissions={
                        RbacPermission.VIEW,
                        RbacPermission.VIEW_ALL,
                        RbacPermission.DEPLOY_MACHINES,
                        RbacPermission.ADMIN_MACHINES,
                    },
                )
            )
        ],
    )
    async def rbac_pools(
        authenticated_user: Optional[AuthenticatedUser] = Depends(
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    @app.post(
        f"{V3_API_PREFIX}/rbac_admin_pools",
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                    rbac_permissions={RbacPermission.EDIT},
                )
            )
        ],
    )
    async def rbac_admin_pools(
        authenticated_user: Optional[AuthenticatedUser] = Depends(
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    @app.post(
        f"{V3_API_PREFIX}/rbac_no_permissions",
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                )
            )
        ],
    )
    async def rbac_no_permissions(
        authenticated_user: Optional[AuthenticatedUser] = Depends(
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    yield app


@pytest.fixture
async def auth_client(
    auth_app: FastAPI, enable_rbac
) -> AsyncIterator[AsyncClient]:
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

    async def test_get_user_rbac(
        self, auth_client: AsyncClient, mock_aioresponse
    ) -> None:
        def mock_allowed_for_user_endpoint(
            perms: list[RbacPermission], response_ids: list[list]
        ):
            rbac_url = "http://rbac.example:5000"
            endpoint = (
                rbac_url
                + "/api/service/v1/resources/resource-pool/allowed-for-user"
            )
            endpoint += "?p=" + "&p=".join([perm for perm in perms])
            endpoint += "&u=test"
            payload = {k: v for (k, v) in zip(perms, response_ids)}
            mock_aioresponse.get(endpoint, payload=payload)

        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.username == "test"
        assert authenticated_user.roles == {UserRole.USER}
        assert authenticated_user.rbac_permissions is None

        mock_allowed_for_user_endpoint(
            [
                RbacPermission.VIEW,
                RbacPermission.VIEW_ALL,
                RbacPermission.DEPLOY_MACHINES,
                RbacPermission.ADMIN_MACHINES,
            ],
            [[""], [1, 2], [3], [4]],
        )
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/rbac_pools",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        # visible_pools is set to all resources (`[""]`), so they are fetched
        # from the db where only the default one with id=0 is present.
        assert authenticated_user.rbac_permissions.visible_pools == {0}
        assert authenticated_user.rbac_permissions.view_all_pools == {1, 2}
        assert authenticated_user.rbac_permissions.deploy_pools == {3}
        assert authenticated_user.rbac_permissions.admin_pools == {4}
        assert authenticated_user.rbac_permissions.edit_pools is None
        assert (
            authenticated_user.rbac_permissions.can_edit_all_resource_pools
            is None
        )

        mock_allowed_for_user_endpoint([RbacPermission.EDIT], [[""]])
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/rbac_admin_pools",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.rbac_permissions.visible_pools is None
        assert authenticated_user.rbac_permissions.view_all_pools is None
        assert authenticated_user.rbac_permissions.deploy_pools is None
        assert authenticated_user.rbac_permissions.admin_pools is None
        assert authenticated_user.rbac_permissions.edit_pools == {0}
        assert (
            authenticated_user.rbac_permissions.can_edit_all_resource_pools
            is True
        )

        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/rbac_no_permissions",
            json=self._build_request("test", {UserRole.USER}),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.rbac_permissions is not None
        assert authenticated_user.rbac_permissions.visible_pools is None
        assert authenticated_user.rbac_permissions.view_all_pools is None
        assert authenticated_user.rbac_permissions.deploy_pools is None
        assert authenticated_user.rbac_permissions.admin_pools is None
        assert authenticated_user.rbac_permissions.edit_pools is None
        assert (
            authenticated_user.rbac_permissions.can_edit_all_resource_pools
            is None
        )
