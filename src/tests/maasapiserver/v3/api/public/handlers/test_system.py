#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import AsyncMock, Mock, patch

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.services import ServiceCollectionV3
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)


class TestSystemApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/system/info"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [Endpoint(method="GET", path=self.BASE_PATH)]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_get_system_info(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.configurations = Mock()
        services_mock.configurations.get = AsyncMock(return_value="3.7.2")

        with patch(
            "maasapiserver.v3.api.public.handlers.system.get_fips_status"
        ) as mock_fips:
            mock_fips.return_value = Mock(enabled=True)
            response = await mocked_api_client_user.get(self.BASE_PATH)

        assert response.status_code == 200
        body = response.json()
        assert body["fips_active"] is True
        assert body["version"] == "3.7.2"

    async def test_get_system_info_not_authenticated(
        self, mocked_api_client: AsyncClient
    ) -> None:
        response = await mocked_api_client.get(self.BASE_PATH)
        assert response.status_code == 401

    async def test_get_system_info_no_version_returns_500(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.configurations = Mock()
        services_mock.configurations.get = AsyncMock(return_value=None)

        with patch(
            "maasapiserver.v3.api.public.handlers.system.get_fips_status"
        ) as mock_fips:
            mock_fips.return_value = Mock(enabled=False)
            response = await mocked_api_client_user.get(self.BASE_PATH)

        assert response.status_code == 500
