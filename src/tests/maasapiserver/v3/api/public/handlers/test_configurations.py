# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.configurations import (
    ConfigurationResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.services import (
    ConfigurationsService,
    ServiceCollectionV3,
)


@pytest.mark.asyncio
class TestConfigurationsApi:
    BASE_PATH = f"{V3_API_PREFIX}/configurations"

    async def test_get_permissions(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = "test"
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/theme")
        assert response.status_code == 200
        config_response = ConfigurationResponse(**response.json())
        assert config_response.kind == "Configuration"
        assert config_response.name == "theme"
        assert config_response.value == "test"

    async def test_get_unexisting_config(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = None
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/unexisting"
        )
        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_private_config(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = None
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/active_discovery_last_scan"
        )
        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404
