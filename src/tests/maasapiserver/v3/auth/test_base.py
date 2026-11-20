# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import AsyncIterator, Iterator, Optional
from unittest.mock import Mock

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.requests import Request
from starlette.responses import Response

from maasapiserver.common.middlewares.exceptions import ExceptionMiddleware
from maasapiserver.v3.auth.base import (
    check_authentication,
    check_permissions,
    get_authenticated_user,
    reject_api_tokens,
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
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.db import Database
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import CacheForServices, OpenFGATupleService
from maasservicelayer.utils.api_tokens import generate_api_token
from tests.fixtures.factories.token import create_test_api_token
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.app import AsyncOpenFGAClientMock
from tests.maasapiserver.fixtures.db import Fixture


def _build_auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
    openfga_permissions: set[MAASResourceEntitlement],
) -> FastAPI:
    app = FastAPI()

    services_cache = CacheForServices()

    app.add_middleware(
        V3AuthenticationMiddleware,
        providers_cache=AuthenticationProvidersCache(
            jwt_authentication_providers=[LocalAuthenticationProvider()],
            oidc_authentication_provider=OIDCAuthenticationProvider(),
        ),
    )

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
    app.add_middleware(ExceptionMiddleware)
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
        f"{V3_API_PREFIX}/reject_api_tokens",
        dependencies=[Depends(reject_api_tokens())],
    )
    async def endpoint_rejecting_api_tokens() -> Response:
        return Response(status_code=200)

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

    return app


@pytest.fixture
def auth_app(
    db: Database,
    db_connection: AsyncConnection,
    transaction_middleware_class: type,
) -> Iterator[FastAPI]:
    # The default app grants CAN_EDIT_GLOBAL_ENTITIES so OpenFGA checks pass.
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
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test/"
    ) as client:
        yield client


@pytest.fixture
async def auth_client_no_permissions(
    auth_app_no_permissions: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=auth_app_no_permissions),
        base_url="http://test/",
    ) as client:
        yield client


async def _pat_raw_token(fixture: Fixture) -> str:
    user = await create_test_user(fixture)
    generated = generate_api_token()
    await create_test_api_token(
        fixture,
        user_id=user.id,
        public_id=generated.public_id,
        secret_hash=generated.secret_hash,
    )
    return generated.raw_token


class TestPermissionsFunctions:
    async def test_check_authentication_ok(
        self, auth_client: AsyncClient, fixture: Fixture
    ) -> None:
        raw_token = await _pat_raw_token(fixture)
        response = await auth_client.post(
            f"{V3_API_PREFIX}/check_auth",
            headers={"Authorization": f"bearer {raw_token}"},
        )
        assert response.status_code == 200

    async def test_check_authentication_unauthenticated(
        self, auth_client: AsyncClient
    ) -> None:
        response = await auth_client.post(f"{V3_API_PREFIX}/check_auth")
        assert response.status_code == 401

    async def test_get_user(
        self, auth_client: AsyncClient, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        generated = generate_api_token()
        await create_test_api_token(
            fixture,
            user_id=user.id,
            public_id=generated.public_id,
            secret_hash=generated.secret_hash,
        )

        user_response = await auth_client.post(
            f"{V3_API_PREFIX}/user",
            headers={"Authorization": f"bearer {generated.raw_token}"},
        )

        assert user_response.status_code == 200
        assert (
            AuthenticatedUser(**user_response.json()).username == user.username
        )

    async def test_permissions_ok(
        self, auth_client: AsyncClient, fixture: Fixture
    ) -> None:
        raw_token = await _pat_raw_token(fixture)
        response = await auth_client.post(
            f"{V3_API_PREFIX}/permissions",
            headers={"Authorization": f"bearer {raw_token}"},
        )
        assert response.status_code == 200

    async def test_permissions_unauthenticated(
        self, auth_client: AsyncClient
    ) -> None:
        response = await auth_client.post(f"{V3_API_PREFIX}/permissions")
        assert response.status_code == 401

    async def test_permissions_forbidden(
        self, auth_client_no_permissions: AsyncClient, fixture: Fixture
    ) -> None:
        raw_token = await _pat_raw_token(fixture)
        response = await auth_client_no_permissions.post(
            f"{V3_API_PREFIX}/permissions",
            headers={"Authorization": f"bearer {raw_token}"},
        )
        assert response.status_code == 403

    async def test_reject_api_tokens_allows_unauthenticated_request(
        self, auth_client: AsyncClient
    ) -> None:
        response = await auth_client.post(f"{V3_API_PREFIX}/reject_api_tokens")
        assert response.status_code == 200

    @pytest.mark.parametrize("scheme", ["bearer", "Bearer", "BEARER"])
    async def test_reject_api_tokens_forbids_api_token(
        self, auth_client: AsyncClient, fixture: Fixture, scheme: str
    ) -> None:
        raw_token = await _pat_raw_token(fixture)
        response = await auth_client.post(
            f"{V3_API_PREFIX}/reject_api_tokens",
            headers={"Authorization": f"{scheme} {raw_token}"},
        )
        assert response.status_code == 403
