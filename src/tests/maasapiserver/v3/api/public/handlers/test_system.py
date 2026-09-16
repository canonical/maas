#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock, patch

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)


class TestSystemApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/system/info"

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        """The subclass should return a list of endpoints that need authentication only."""
        return [Endpoint(method="GET", path=self.BASE_PATH)]

    async def test_get_system_info_user(
        self,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        with patch(
            "maasapiserver.v3.api.public.handlers.system.get_fips_status"
        ) as mock_fips:
            with patch(
                "maasapiserver.v3.api.public.handlers.system.get_running_version"
            ) as mock_version:
                with patch(
                    "maasapiserver.v3.api.public.handlers.system.is_hardening_enabled"
                ) as mock_hardening:
                    mock_hardening.return_value = True
                    mock_version.return_value = Mock(short_version="3.7.2")
                    mock_fips.return_value = Mock(enabled=True)
                    response = await mocked_api_client_user.get(self.BASE_PATH)

        assert response.status_code == 200
        body = response.json()
        assert body["fips_active"] is True
        assert body["version"] == "3.7.2"
        assert body["hardening_active"] is True

    async def test_get_system_info_not_authenticated(
        self, mocked_api_client: AsyncClient
    ) -> None:
        response = await mocked_api_client.get(self.BASE_PATH)
        assert response.status_code == 401
