from datetime import datetime, timedelta
from typing import AsyncIterator, Iterator

from aioresponses import aioresponses
from django.core import signing
from fastapi import FastAPI
from httpx import AsyncClient, Headers
from macaroonbakery import bakery
import pytest

from maasapiserver.common.utils.date import utcnow
from maasapiserver.main import create_app
from maasapiserver.settings import Config
from maasapiserver.v2.models.entities.user import User
from maasapiserver.v3.api.models.responses.oauth2 import AccessTokenResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.db import Database
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture


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
            "key": "mykey",
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
def mock_aioresponse():
    with aioresponses() as m:
        yield m
