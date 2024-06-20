from httpx import AsyncClient
from jose import jwt
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.oauth2 import AccessTokenResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestAuthApi:
    # POST /auth/login
    async def test_post(
        self, api_client: AsyncClient, fixture: Fixture
    ) -> None:
        created_user = await create_test_user(fixture)
        response = await api_client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": created_user.username, "password": "test"},
        )
        assert response.status_code == 200

        token_response = AccessTokenResponse(**response.json())
        assert token_response.token_type == "bearer"
        assert (
            jwt.get_unverified_claims(token_response.access_token)["sub"]
            == created_user.username
        )

    async def test_post_validation_failed(
        self, api_client: AsyncClient, fixture: Fixture
    ) -> None:
        created_user = await create_test_user(fixture)
        response = await api_client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": created_user.username},
        )
        assert response.status_code == 422

        response = await api_client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": created_user.username},
        )
        assert response.status_code == 422

    async def test_post_wrong_credentials(
        self, api_client: AsyncClient, fixture: Fixture
    ) -> None:
        created_user = await create_test_user(fixture)
        response = await api_client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": created_user.username, "password": "wrong"},
        )
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

        response = await api_client.post(
            f"{V3_API_PREFIX}/auth/login",
            data={"username": "wrong", "password": "test"},
        )
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401
