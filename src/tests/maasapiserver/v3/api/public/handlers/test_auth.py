#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from json import dumps as _dumps
from unittest.mock import AsyncMock, Mock, patch

from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from jose import jwt
from macaroonbakery.bakery import Macaroon
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.common.models.constants import (
    UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    DischargeRequiredException,
    UnauthorizedException,
)
from maasapiserver.v3.api.public.models.responses.oauth2 import (
    AccessTokenResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3
from maasapiserver.v3.services.auth import AuthService
from maasapiserver.v3.services.external_auth import ExternalAuthService
from maasservicelayer.auth.jwt import JWT, UserRole


@pytest.mark.asyncio
class TestAuthApi:
    BASE_PATH = f"{V3_API_PREFIX}/auth"

    # POST /auth/login
    async def test_post(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login = AsyncMock(
            return_value=JWT.create("key", "username", [UserRole.USER])
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login",
            data={"username": "username", "password": "test"},
        )
        assert response.status_code == 200

        token_response = AccessTokenResponse(**response.json())
        assert token_response.token_type == "bearer"
        assert (
            jwt.get_unverified_claims(token_response.access_token)["sub"]
            == "username"
        )

    async def test_post_validation_failed(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login = AsyncMock(
            side_effect=RequestValidationError(errors=[])
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login", data={"username": "username"}
        )

        assert response.status_code == 422

    async def test_post_discharge_required_exception(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)
        services_mock.external_auth.raise_discharge_required_exception = (
            AsyncMock(
                side_effect=DischargeRequiredException(macaroon=Mock(Macaroon))
            )
        )

        # we have to mock json.dumps as it doesn't know how to deal with Mock objects
        def custom_json_dumps(*args, **kwargs):
            return _dumps(*args, **(kwargs | {"default": lambda obj: "mock"}))

        with patch("json.dumps", custom_json_dumps):
            response = await mocked_api_client_rbac.post(
                f"{self.BASE_PATH}/login",
                data={"username": "username", "password": "test"},
            )

        services_mock.external_auth.raise_discharge_required_exception.assert_called_once()
        assert response.status_code == 401
        json_response = response.json()
        assert json_response["Code"] == "macaroon discharge required"

    async def test_post_wrong_credentials(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login = AsyncMock(
            side_effect=UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
                        message="The credentials are not matching or the user does not exist",
                    )
                ]
            )
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login",
            data={"username": "username", "password": "wrong"},
        )
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

    # GET /auth/access_token
    async def test_get_access_token_with_jwt(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.access_token = AsyncMock(
            return_value=JWT.create("key", "username", [UserRole.USER])
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/access_token",
        )
        assert response.status_code == 200

        token_response = AccessTokenResponse(**response.json())
        assert token_response.kind == "AccessToken"
        assert token_response.token_type == "bearer"
        assert (
            jwt.get_unverified_claims(token_response.access_token)["sub"]
            == "username"
        )

    async def test_get_access_token_with_session_id(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_session_id: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.access_token = AsyncMock(
            return_value=JWT.create("key", "username", [UserRole.USER])
        )
        response = await mocked_api_client_session_id.get(
            f"{self.BASE_PATH}/access_token",
        )
        assert response.status_code == 200

        token_response = AccessTokenResponse(**response.json())
        assert token_response.kind == "AccessToken"
        assert token_response.token_type == "bearer"
        assert (
            jwt.get_unverified_claims(token_response.access_token)["sub"]
            == "username"
        )

    @pytest.mark.skip
    async def test_get_access_token_with_macaroon():
        pass

    async def test_get_access_token_not_logged_in(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/access_token"
        )
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401
