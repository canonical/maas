# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from json import JSONDecodeError
from typing import AsyncIterator, Awaitable, Callable, Iterator, Optional
from unittest.mock import Mock

from fastapi import Depends, FastAPI
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.v3.auth.base import (
    check_authentication,
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.middlewares.context import ContextMiddleware
from maasapiserver.v3.middlewares.services import ServicesMiddleware
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.db import Database
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.exceptions.catalog import (
    DischargeRequiredException,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import CacheForServices, OpenFGATupleService
from tests.maasapiserver.fixtures.app import AsyncOpenFGAClientMock


class AuthTestMiddleware(BaseHTTPMiddleware):
    """
    This middleware assumes that every request body is an AuthenticatedUser and set it in the request context. We have to do
    this because the dependency injection mechanism of fastapi is lacking of flexibility and forces us to go through an endpoint
    to test a function that uses `Depends`. See https://github.com/tiangolo/fastapi/discussions/7720 .
    This is a workaround to make the testing of the permission functions "easier".
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


def _build_auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
    openfga_permissions: set[MAASResourceEntitlement],
) -> FastAPI:
    app = FastAPI()

    services_cache = CacheForServices()

    app.add_middleware(AuthTestMiddleware)

    # Let the ServicesMiddleware populate the request.state.services with a concrete instance of the services, then override the openfga_tuples service with a mock that returns the permissions we want for testing.
    from maasapiserver.v3.api import services as services_dep

    original_services_dep = services_dep

    openfga_mock = AsyncOpenFGAClientMock(openfga_permissions)

    async def patched_services(request: Request):
        svc = request.state.services
        svc.openfga_tuples = Mock(OpenFGATupleService)
        svc.openfga_tuples.get_client.return_value = openfga_mock
        return svc

    app.add_middleware(ServicesMiddleware, cache=services_cache)
    app.add_middleware(transaction_middleware_class, db=db)
    app.add_middleware(ContextMiddleware)

    app.add_event_handler("shutdown", services_cache.close)

    # Override the FastAPI services dependency to use the patched version that returns the mocked OpenFGA client.
    app.dependency_overrides[original_services_dep] = patched_services

    @app.post(
        f"{V3_API_PREFIX}/check_auth",
        dependencies=[Depends(check_authentication())],
    )
    async def check_auth_endpoint() -> Response:
        return Response(status_code=200)

    @app.post(f"{V3_API_PREFIX}/user")
    async def get_user(
        authenticated_user: Optional[AuthenticatedUser] = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    @app.post(
        f"{V3_API_PREFIX}/permissions",
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES,
                )
            )
        ],
    )
    async def endpoint_with_permissions() -> Response:
        return Response(status_code=200)

    @app.post(
        f"{V3_API_PREFIX}/rbac_pools",
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
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
        authenticated_user: Optional[AuthenticatedUser] = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    @app.post(
        f"{V3_API_PREFIX}/rbac_admin_pools",
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES,
                    rbac_permissions={RbacPermission.EDIT},
                )
            )
        ],
    )
    async def rbac_admin_pools(
        authenticated_user: Optional[AuthenticatedUser] = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    @app.post(
        f"{V3_API_PREFIX}/rbac_no_permissions",
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
                )
            )
        ],
    )
    async def rbac_no_permissions(
        authenticated_user: Optional[AuthenticatedUser] = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> Optional[AuthenticatedUser]:
        return authenticated_user

    return app


@pytest.fixture
def auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    # The default app grants CAN_EDIT_GLOBAL_ENTITIES so that all non-RBAC endpoints pass the OpenFGA check.
    yield _build_auth_app(
        db,
        db_connection,
        transaction_middleware_class,
        openfga_permissions={
            MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
            MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES,
        },
    )


@pytest.fixture
def auth_app_no_permissions(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    # App where the user has no OpenFGA permissions, used to test forbidden responses.
    yield _build_auth_app(
        db,
        db_connection,
        transaction_middleware_class,
        openfga_permissions=set(),
    )


@pytest.fixture
async def auth_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=auth_app, base_url="http://test/") as client:
        yield client


@pytest.fixture
async def auth_client_no_permissions(
    auth_app_no_permissions: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=auth_app_no_permissions, base_url="http://test/"
    ) as client:
        yield client


@pytest.fixture
async def auth_client_candid(
    auth_app: FastAPI, enable_candid
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=auth_app, base_url="http://test/") as client:
        yield client


@pytest.fixture
async def auth_client_rbac(
    auth_app: FastAPI, enable_rbac
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=auth_app, base_url="http://test/") as client:
        yield client


class TestPermissionsFunctions:
    @staticmethod
    def _build_request(username: str) -> dict:
        return jsonable_encoder(AuthenticatedUser(id=0, username=username))

    async def test_check_authentication_ok(
        self, auth_client: AsyncClient
    ) -> None:
        response = await auth_client.post(
            f"{V3_API_PREFIX}/check_auth",
            json=self._build_request("test"),
        )
        assert response.status_code == 200

    async def test_check_authentication_unauthenticated(
        self, auth_client: AsyncClient
    ) -> None:
        response = await auth_client.post(f"{V3_API_PREFIX}/check_auth")
        assert response.status_code == 401

    async def test_get_user(self, auth_client: AsyncClient) -> None:
        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user",
            json=self._build_request("test"),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.username == "test"

    async def test_permissions_ok(self, auth_client: AsyncClient) -> None:
        response = await auth_client.post(
            f"{V3_API_PREFIX}/permissions",
            json=self._build_request("test"),
        )
        assert response.status_code == 200

    async def test_permissions_unauthenticated(
        self, auth_client: AsyncClient
    ) -> None:
        response = await auth_client.post(f"{V3_API_PREFIX}/permissions")
        assert response.status_code == 401

    async def test_permissions_forbidden(
        self, auth_client_no_permissions: AsyncClient
    ) -> None:
        response = await auth_client_no_permissions.post(
            f"{V3_API_PREFIX}/permissions",
            json=self._build_request("test"),
        )
        assert response.status_code == 403

    async def test_check_permissions_requires_at_least_one_arg(self) -> None:
        with pytest.raises(ValueError, match="At least one"):
            check_permissions()

    async def test_get_user_candid(
        self, auth_client_candid: AsyncClient
    ) -> None:
        user_response = await auth_client_candid.post(
            f"{V3_API_PREFIX}/user",
            json=self._build_request("test"),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.username == "test"
        assert authenticated_user.rbac_permissions is None

        # Candid auth skips the OpenFGA check, so the endpoint should
        # succeed even though no openfga_permission is granted by the mock.
        user_response = await auth_client_candid.post(
            f"{V3_API_PREFIX}/rbac_pools",
            json=self._build_request("test"),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.rbac_permissions is None

        user_response = await auth_client_candid.post(
            f"{V3_API_PREFIX}/rbac_admin_pools",
            json=self._build_request("test"),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.rbac_permissions is None

        user_response = await auth_client_candid.post(
            f"{V3_API_PREFIX}/rbac_no_permissions",
            json=self._build_request("test"),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.rbac_permissions is None

    async def test_get_user_rbac(
        self, auth_client_rbac: AsyncClient, mock_aioresponse
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

        user_response = await auth_client_rbac.post(
            f"{V3_API_PREFIX}/user",
            json=self._build_request("test"),
        )
        assert user_response.status_code == 200
        authenticated_user = AuthenticatedUser(**user_response.json())
        assert authenticated_user.username == "test"
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
        user_response = await auth_client_rbac.post(
            f"{V3_API_PREFIX}/rbac_pools",
            json=self._build_request("test"),
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
        user_response = await auth_client_rbac.post(
            f"{V3_API_PREFIX}/rbac_admin_pools",
            json=self._build_request("test"),
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

        user_response = await auth_client_rbac.post(
            f"{V3_API_PREFIX}/rbac_no_permissions",
            json=self._build_request("test"),
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
