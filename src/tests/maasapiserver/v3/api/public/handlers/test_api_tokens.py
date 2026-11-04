#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.api_tokens import (
    ApiTokenCreatedResponse,
    ApiTokensListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.tokens import ApiToken
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.api_tokens import ApiTokenService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_TOKEN = ApiToken(
    id=1,
    name="ci",
    public_id="e623c3c3b9b63c3b",
    secret_hash="0" * 64,
    expires_at=utcnow() + timedelta(days=1),
    user_id=1,
)


class TestApiTokensApi(ApiCommonTests):
    ME_PATH = f"{V3_API_PREFIX}/users/me/pats"
    ADMIN_PATH = f"{V3_API_PREFIX}/pats"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.ADMIN_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.ADMIN_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
            ),
            Endpoint(
                method="DELETE",
                path=f"{self.ADMIN_PATH}/1",
                permission=MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
            ),
        ]

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.ME_PATH),
            Endpoint(method="GET", path=f"{self.ME_PATH}/1"),
            Endpoint(method="POST", path=self.ME_PATH),
            Endpoint(method="DELETE", path=f"{self.ME_PATH}/1"),
        ]

    async def test_create_returns_raw_token_once(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.api_tokens = Mock(ApiTokenService)
        services_mock.api_tokens.create_token.return_value = (
            TEST_TOKEN,
            "maas_pat_raw",
        )

        response = await mocked_api_client_user.post(
            self.ME_PATH,
            json={
                "name": "ci",
                "expires_at": (utcnow() + timedelta(days=1)).isoformat(),
            },
        )

        assert response.status_code == 201
        body = ApiTokenCreatedResponse(**response.json())
        assert body.token == "maas_pat_raw"
        assert "secret_hash" not in response.json()

    @pytest.mark.parametrize(
        "expires_at",
        [
            (utcnow() - timedelta(days=1)).isoformat(),
            "2999-01-01T00:00:00",
        ],
    )
    async def test_create_rejects_invalid_expiration(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
        expires_at: str,
    ) -> None:
        services_mock.api_tokens = Mock(ApiTokenService)

        response = await mocked_api_client_user.post(
            self.ME_PATH, json={"name": "ci", "expires_at": expires_at}
        )

        assert response.status_code == 422
        services_mock.api_tokens.create_token.assert_not_called()

    async def test_list_has_next_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.api_tokens = Mock(ApiTokenService)
        services_mock.api_tokens.list.return_value = ListResult[ApiToken](
            items=[TEST_TOKEN], total=2
        )

        response = await mocked_api_client_user.get(
            f"{self.ME_PATH}?size=1&include_revoked=true"
        )

        assert response.status_code == 200
        body = ApiTokensListResponse(**response.json())
        assert body.next == (
            f"{self.ME_PATH}?page=2&size=1&include_revoked=true"
        )

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.api_tokens = Mock(ApiTokenService)
        services_mock.api_tokens.get_one.return_value = None

        response = await mocked_api_client_user.get(f"{self.ME_PATH}/1")

        assert response.status_code == 404

    async def test_delete_revokes(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.api_tokens = Mock(ApiTokenService)
        services_mock.api_tokens.get_one.return_value = TEST_TOKEN

        response = await mocked_api_client_user.delete(f"{self.ME_PATH}/1")

        assert response.status_code == 204
        services_mock.api_tokens.revoke.assert_awaited_once_with(TEST_TOKEN)
