# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from ipaddress import IPv4Address
from unittest.mock import ANY, Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.configurations import (
    UpdateConfigurationRequest,
)
from maasapiserver.v3.api.public.models.responses.configurations import (
    ConfigurationResponse,
    ConfigurationsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.events import EventTypeEnum
from maascommon.events import EVENT_DETAILS_MAP
from maasservicelayer.models.configurations import (
    ConfigFactory,
    MAASNameConfig,
    ThemeConfig,
)
from maasservicelayer.models.events import EndpointChoicesEnum
from maasservicelayer.services import (
    ConfigurationsService,
    EventsService,
    ServiceCollectionV3,
)


@pytest.mark.asyncio
class TestConfigurationsApi:
    BASE_PATH = f"{V3_API_PREFIX}/configurations"

    async def test_get_configurations_forbidden_for_users(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?name=theme"
        )
        assert response.status_code == 403
        config_response = ErrorBodyResponse(**response.json())
        assert config_response.kind == "Error"

    async def test_get_configurations_empty(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {}
        response = await mocked_api_client_admin.get(f"{self.BASE_PATH}")
        assert response.status_code == 200
        configs_response = ConfigurationsListResponse(**response.json())
        assert configs_response.kind == "ConfigurationsList"
        assert len(configs_response.items) == 0
        services_mock.configurations.get_many.assert_called_once_with(set())

    async def test_get_configurations(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            ThemeConfig.name: ThemeConfig.default,
            MAASNameConfig.name: MAASNameConfig.default,
        }
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}&name={MAASNameConfig.name}"
        )
        assert response.status_code == 200
        configs_response = ConfigurationsListResponse(**response.json())
        assert configs_response.kind == "ConfigurationsList"
        assert len(configs_response.items) == 2
        assert sorted(configs_response.items, key=lambda x: x.name) == [
            ConfigurationResponse(
                name=MAASNameConfig.name, value=MAASNameConfig.default
            ),
            ConfigurationResponse(
                name=ThemeConfig.name, value=ThemeConfig.default
            ),
        ]
        services_mock.configurations.get_many.assert_called_once_with(
            {ThemeConfig.name, MAASNameConfig.name}
        )

    @pytest.mark.parametrize(
        "name",
        [
            config_name
            for config_name, config_model in ConfigFactory.ALL_CONFIGS.items()
            if not config_model.is_public
        ],
    )
    async def test_get_private_configs(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        name: str,
    ):
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}&name={name}"
        )
        assert response.status_code == 422
        configs_response = ErrorBodyResponse(**response.json())
        assert configs_response.kind == "Error"

    async def test_get_configuration(
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
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    @pytest.mark.parametrize(
        "name",
        [
            config_name
            for config_name, config_model in ConfigFactory.ALL_CONFIGS.items()
            if not config_model.is_public
        ],
    )
    async def test_get_private_config(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
        name: str,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/{name}")
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    @pytest.mark.parametrize(
        "name",
        [
            config_name
            for config_name, config_model in ConfigFactory.ALL_CONFIGS.items()
            if not config_model.is_public
        ],
    )
    async def test_set_private_config(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        name: str,
    ):
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{name}", json={"name": name, "value": None}
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_set_config_forbidden_for_users(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        response = await mocked_api_client_user.put(
            f"{self.BASE_PATH}/theme",
            json=jsonable_encoder(UpdateConfigurationRequest(value=None)),
        )
        assert response.status_code == 403
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403

    async def test_set_config_for_admins(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.events = Mock(EventsService)
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/theme",
            json=jsonable_encoder(UpdateConfigurationRequest(value=None)),
        )
        assert response.status_code == 200
        configuration_response = ConfigurationResponse(**response.json())
        assert configuration_response.kind == "Configuration"
        assert configuration_response.name == "theme"
        assert configuration_response.value is None
        services_mock.configurations.set.assert_awaited_once_with(
            "theme", None
        )
        services_mock.events.record_event.assert_awaited_once_with(
            event_type=EventTypeEnum.SETTINGS,
            event_action=EVENT_DETAILS_MAP[EventTypeEnum.SETTINGS].description,
            event_description="Updated configuration setting 'theme' to 'None'.",
            user_agent=ANY,
            ip_address=IPv4Address("127.0.0.1"),
            user="username",
            endpoint=EndpointChoicesEnum.API,
        )

    async def test_set_config_type_mismatch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/theme",
            json=jsonable_encoder(UpdateConfigurationRequest(value={})),
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
