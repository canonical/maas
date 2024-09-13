from datetime import datetime, timedelta
from typing import AsyncIterator, Awaitable, Callable, Iterator
from unittest.mock import AsyncMock, Mock

from aioresponses import aioresponses
from django.core import signing
from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient, Headers
from macaroonbakery import bakery
import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from maasapiserver.common.middlewares.exceptions import (
    ExceptionHandlers,
    ExceptionMiddleware,
)
from maasapiserver.main import create_app
from maasapiserver.settings import Config
from maasapiserver.v3.api.public.handlers import APIv3
from maasapiserver.v3.api.public.models.responses.oauth2 import (
    AccessTokenResponse,
)
from maasapiserver.v3.auth.base import AuthenticatedUser
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db import Database
from maasservicelayer.models.users import User
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture

RBAC_URL = "http://rbac.example.com"


def create_app_with_mocks(
    mocked_services: ServiceCollectionV3,
    roles: set[UserRole] | None = None,
    external_auth: bool = False,
):
    class InjectServicesMocks(BaseHTTPMiddleware):
        async def dispatch(
            self,
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            request.state.services = mocked_services
            if external_auth:
                request.state.services.external_auth.get_external_auth = (
                    AsyncMock(
                        return_value=ExternalAuthConfig(
                            type=ExternalAuthType.RBAC,
                            url=RBAC_URL,
                            domain="",
                            admin_group="",
                        )
                    )
                )
            else:
                request.state.services.external_auth = Mock(
                    ExternalAuthService
                )
                request.state.services.external_auth.get_external_auth = (
                    AsyncMock(return_value=None)
                )
            return await call_next(request)

    class InjectUserInRequest(BaseHTTPMiddleware):
        async def dispatch(
            self,
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            if roles:
                request.state.authenticated_user = AuthenticatedUser(
                    username="username", roles=roles
                )
            else:
                request.state.authenticated_user = None
            return await call_next(request)

    app = FastAPI(
        title="MAASAPIServer",
        name="maasapiserver",
    )
    api = APIv3

    app.add_middleware(InjectUserInRequest)
    app.add_middleware(InjectServicesMocks)
    app.add_middleware(ExceptionMiddleware)
    app.add_exception_handler(
        RequestValidationError, ExceptionHandlers.validation_exception_handler
    )
    api.register(app.router)
    return app


@pytest.fixture
def services_mock():
    yield Mock(ServiceCollectionV3)


@pytest.fixture
def app_with_mocked_services(services_mock: ServiceCollectionV3):
    yield create_app_with_mocks(services_mock)


@pytest.fixture
def app_with_mocked_services_admin(services_mock: ServiceCollectionV3):
    yield create_app_with_mocks(services_mock, {UserRole.USER, UserRole.ADMIN})


@pytest.fixture
def app_with_mocked_services_user(services_mock: ServiceCollectionV3):
    yield create_app_with_mocks(services_mock, {UserRole.USER})


@pytest.fixture
def app_with_mocked_services_rbac(services_mock: ServiceCollectionV3):
    yield create_app_with_mocks(services_mock, external_auth=True)


@pytest.fixture
def app_with_mocked_services_user_rbac(services_mock: ServiceCollectionV3):
    yield create_app_with_mocks(
        services_mock, {UserRole.USER}, external_auth=True
    )


@pytest.fixture
async def mocked_api_client(
    app_with_mocked_services: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=app_with_mocked_services, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def mocked_api_client_user(
    app_with_mocked_services_user: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=app_with_mocked_services_user, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def mocked_api_client_admin(
    app_with_mocked_services_admin: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=app_with_mocked_services_admin, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def mocked_api_client_session_id(
    app_with_mocked_services_user: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=app_with_mocked_services_user, base_url="http://test"
    ) as client:
        client.cookies.set("sessionid", "fakesessionid")
        yield client


@pytest.fixture
async def mocked_api_client_rbac(
    app_with_mocked_services_rbac: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=app_with_mocked_services_rbac, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def mocked_api_client_user_rbac(
    app_with_mocked_services_user_rbac: FastAPI,
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        app=app_with_mocked_services_user_rbac, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def api_app(
    test_config: Config, transaction_middleware_class: type, db: Database
) -> Iterator[FastAPI]:
    """The API application."""
    yield await create_app(
        config=test_config,
        transaction_middleware_class=transaction_middleware_class,
        db=db,
    )


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Client for the API."""
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def user_session_id(fixture: Fixture) -> Iterator[str]:
    """API user session ID."""
    yield fixture.random_string()


@pytest.fixture
async def authenticated_user(
    fixture: Fixture,
    user_session_id: str,
) -> AsyncIterator[User]:
    user_details = {
        "username": "user",
        "first_name": "Some",
        "last_name": "User",
        "email": "user@example.com",
        "password": "secret",
        "is_superuser": False,
        "is_staff": False,
        "is_active": True,
        "date_joined": datetime.utcnow(),
    }
    [user_details] = await fixture.create("auth_user", user_details)
    user = User(**user_details)
    await _create_user_session(fixture, user, user_session_id)
    yield user


async def _create_user_session(
    fixture: Fixture, user: User, session_id: str
) -> None:
    key = "<UNUSED>"
    salt = "django.contrib.sessions.SessionStore"
    algorithm = "sha256"
    signer = signing.TimestampSigner(key, salt=salt, algorithm=algorithm)
    session_data = signer.sign_object(
        {"_auth_user_id": str(user.id)}, serializer=signing.JSONSerializer
    )
    await fixture.create(
        "django_session",
        {
            "session_key": session_id,
            "session_data": session_data,
            "expire_date": datetime.utcnow() + timedelta(days=20),
        },
    )


@pytest.fixture
async def authenticated_api_client(
    api_app: FastAPI, authenticated_user: User, user_session_id: str
) -> AsyncIterator[AsyncClient]:
    """Authenticated client for the API."""
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        client.cookies.set("sessionid", user_session_id)
        yield client


@pytest.fixture
async def authenticated_admin_api_client_v3(
    api_app: FastAPI, fixture: Fixture
) -> AsyncIterator[AsyncClient]:
    """Authenticated admin client for the V3 API."""
    params = {"is_superuser": True, "username": "admin"}
    created_user = await create_test_user(fixture, **params)
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        response = await client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": created_user.username, "password": "test"},
        )
        token_response = AccessTokenResponse(**response.json())
        client.headers = Headers(
            {"Authorization": "bearer " + token_response.access_token}
        )
        yield client


@pytest.fixture
async def authenticated_user_api_client_v3(
    api_app: FastAPI, fixture: Fixture
) -> AsyncIterator[AsyncClient]:
    """Authenticated user client for the V3 API."""
    params = {"is_superuser": False, "username": "user"}
    created_user = await create_test_user(fixture, **params)
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        response = await client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": created_user.username, "password": "test"},
        )
        token_response = AccessTokenResponse(**response.json())
        client.headers = Headers(
            {"Authorization": "bearer " + token_response.access_token}
        )
        yield client


@pytest.fixture
async def enable_rbac(fixture: Fixture, mock_aioresponse) -> None:
    """
    Enable rbac by inserting the config in the db.
    Mock also an HTTP call to the fake rbac server. If this fixture is used in
    other tests it may need to be modified to mock other HTTP calls.
    """
    rbac_url = "http://rbac.example:5000"
    now = utcnow()
    external_auth_config = {
        "path": "global/external-auth",
        "created": now,
        "updated": now,
        "value": {
            "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            "url": "",
            "user": "admin@candid",
            "domain": "",
            "rbac-url": rbac_url,
            "admin-group": "admin",
        },
    }
    key = bakery.generate_key()
    await fixture.create("maasserver_secret", [external_auth_config])
    mock_aioresponse.get(
        f"{rbac_url}/auth/discharge/info",
        payload={
            "Version": bakery.LATEST_VERSION,
            "PublicKey": str(key.public_key),
        },
    )


@pytest.fixture
async def enable_candid(fixture: Fixture) -> None:
    """
    Enable candid by inserting the config in the db.
    """
    candid_url = "http://candid.example.com"
    now = utcnow()
    external_auth_config = {
        "path": "global/external-auth",
        "created": now,
        "updated": now,
        "value": {
            "key": "mykey",
            "url": candid_url,
            "user": "admin@candid",
            "domain": "",
            "rbac-url": "",
            "admin-group": "admin",
        },
    }
    await fixture.create("maasserver_secret", [external_auth_config])


@pytest.fixture
def mock_aioresponse():
    with aioresponses() as m:
        yield m
