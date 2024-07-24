import json

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.users import UserInfoResponse
from maasapiserver.v3.constants import V3_API_PREFIX


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestUsersApi:
    # GET /users/me
    async def test_get_user_info(
        self, authenticated_user_api_client_v3: AsyncClient
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/users/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.username == "user"
        assert user_info.is_superuser is False

    async def test_get_user_info_admin(
        self, authenticated_admin_api_client_v3: AsyncClient
    ) -> None:
        response = await authenticated_admin_api_client_v3.get(
            f"{V3_API_PREFIX}/users/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.username == "admin"
        assert user_info.is_superuser is True

    async def test_get_user_info_unauthorized(
        self, api_client: AsyncClient
    ) -> None:
        response = await api_client.get(f"{V3_API_PREFIX}/users/me")
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

    async def test_get_user_info_discharge_required(
        self, api_client: AsyncClient, enable_rbac
    ):
        """If external auth is enabled make sure we receive a discharge required response"""
        response = await api_client.get(f"{V3_API_PREFIX}/users/me")
        assert response.status_code == 401
        discharge_response = json.loads(response.content.decode("utf-8"))
        assert discharge_response["Code"] == "macaroon discharge required"
        assert discharge_response["Info"]["Macaroon"] is not None
        assert discharge_response["Info"]["MacaroonPath"] == "/"
        assert discharge_response["Info"]["CookieNameSuffix"] == "maas"
