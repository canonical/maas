# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from ipaddress import IPv4Address
from typing import Callable
from unittest.mock import ANY, call, Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.configurations import (
    PublicConfigName,
    UpdateConfigurationItemRequest,
    UpdateConfigurationRequest,
    UpdateConfigurationsRequest,
)
from maasapiserver.v3.api.public.models.responses.configurations import (
    ConfigurationResponse,
    ConfigurationsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.events import EventTypeEnum
from maascommon.events import EVENT_DETAILS_MAP
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.models.configurations import (
    ConfigFactory,
    MAASNameConfig,
    ThemeConfig,
    UseRackProxyConfig,
)
from maasservicelayer.models.events import EndpointChoicesEnum
from maasservicelayer.services import (
    ConfigurationsService,
    EventsService,
    HookedConfigurationsService,
    ServiceCollectionV3,
)
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)


@pytest.mark.asyncio
class TestConfigurationsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/configurations"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="PUT",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
                rbac_admin_permission=True,
            ),
            Endpoint(
                method="PUT",
                path=f"{self.BASE_PATH}/{ThemeConfig.name}",
                permission=MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
                rbac_admin_permission=True,
            ),
        ]

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}?name={ThemeConfig.name}",
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/{ThemeConfig.name}",
            ),
        ]

    async def test_get_configurations_unrestricted_without_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(None)
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            ThemeConfig.name: ThemeConfig.default,
        }
        response = await client.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}"
        )
        assert response.status_code == 200
        configs_response = ConfigurationsListResponse(**response.json())
        assert configs_response.kind == "ConfigurationsList"
        assert len(configs_response.items) == 1

    async def test_get_configurations_restricted_without_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(None)
        services_mock.configurations = Mock(ConfigurationsService)
        response = await client.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}&name={UseRackProxyConfig.name}"
        )
        assert response.status_code == 403
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403
        services_mock.configurations.get_many.assert_not_called()

    async def test_get_configurations_restricted_with_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            UseRackProxyConfig.name: UseRackProxyConfig.default,
        }
        response = await client.get(
            f"{self.BASE_PATH}?name={UseRackProxyConfig.name}"
        )
        assert response.status_code == 200
        configs_response = ConfigurationsListResponse(**response.json())
        assert configs_response.items == [
            ConfigurationResponse(
                name=UseRackProxyConfig.name,
                value=UseRackProxyConfig.default,
            )
        ]

    async def test_get_configurations_empty(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {}
        response = await client.get(f"{self.BASE_PATH}")
        assert response.status_code == 200
        configs_response = ConfigurationsListResponse(**response.json())
        assert configs_response.kind == "ConfigurationsList"
        assert len(configs_response.items) == 0
        services_mock.configurations.get_many.assert_called_once_with(set())

    async def test_get_configurations(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            ThemeConfig.name: ThemeConfig.default,
            MAASNameConfig.name: MAASNameConfig.default,
        }
        response = await client.get(
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
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        name: str,
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        response = await client.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}&name={name}"
        )
        assert response.status_code == 422
        configs_response = ErrorBodyResponse(**response.json())
        assert configs_response.kind == "Error"

    async def test_get_configuration_unrestricted_without_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(None)
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = "test"
        response = await client.get(f"{self.BASE_PATH}/{ThemeConfig.name}")
        assert response.status_code == 200
        config_response = ConfigurationResponse(**response.json())
        assert config_response.kind == "Configuration"
        assert config_response.name == ThemeConfig.name
        assert config_response.value == "test"

    async def test_get_configuration_restricted_without_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(None)
        services_mock.configurations = Mock(ConfigurationsService)
        response = await client.get(
            f"{self.BASE_PATH}/{UseRackProxyConfig.name}"
        )
        assert response.status_code == 403
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403
        services_mock.configurations.get.assert_not_called()

    async def test_get_configuration_restricted_with_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = (
            UseRackProxyConfig.default
        )
        response = await client.get(
            f"{self.BASE_PATH}/{UseRackProxyConfig.name}"
        )
        assert response.status_code == 200
        config_response = ConfigurationResponse(**response.json())
        assert config_response.name == UseRackProxyConfig.name
        assert config_response.value == UseRackProxyConfig.default

    async def test_get_configuration(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = "test"
        response = await client.get(f"{self.BASE_PATH}/theme")
        assert response.status_code == 200
        config_response = ConfigurationResponse(**response.json())
        assert config_response.kind == "Configuration"
        assert config_response.name == "theme"
        assert config_response.value == "test"

    async def test_get_unexisting_config(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = None
        response = await client.get(f"{self.BASE_PATH}/unexisting")
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
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        name: str,
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
        )
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = None
        response = await client.get(f"{self.BASE_PATH}/{name}")
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
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        name: str,
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
        )
        response = await client.put(
            f"{self.BASE_PATH}/{name}", json={"name": name, "value": None}
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_set_config_forbidden_for_users_without_permissions(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(None)
        response = await client.put(
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
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
        )
        services_mock.hooked_configurations = Mock(HookedConfigurationsService)
        services_mock.events = Mock(EventsService)
        response = await client.put(
            f"{self.BASE_PATH}/theme",
            json=jsonable_encoder(UpdateConfigurationRequest(value=None)),
        )
        assert response.status_code == 200
        configuration_response = ConfigurationResponse(**response.json())
        assert configuration_response.kind == "Configuration"
        assert configuration_response.name == "theme"
        assert configuration_response.value is None
        services_mock.hooked_configurations.set.assert_awaited_once_with(
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
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
        )
        response = await client.put(
            f"{self.BASE_PATH}/theme",
            json=jsonable_encoder(UpdateConfigurationRequest(value={})),
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_set_configs_forbidden_for_users(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(None)
        response = await client.put(
            self.BASE_PATH,
            json=jsonable_encoder(
                UpdateConfigurationsRequest(
                    configurations=[
                        UpdateConfigurationItemRequest(
                            name=PublicConfigName.THEME, value=None
                        )
                    ]
                )
            ),
        )
        assert response.status_code == 403
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403

    async def test_set_configs_for_admins(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
        )
        services_mock.hooked_configurations = Mock(HookedConfigurationsService)
        services_mock.events = Mock(EventsService)
        response = await client.put(
            self.BASE_PATH,
            json=jsonable_encoder(
                UpdateConfigurationsRequest(
                    configurations=[
                        UpdateConfigurationItemRequest(
                            name=PublicConfigName.THEME, value=None
                        ),
                        UpdateConfigurationItemRequest(
                            name=PublicConfigName.USE_RACK_PROXY, value=False
                        ),
                    ]
                )
            ),
        )
        assert response.status_code == 204
        services_mock.hooked_configurations.set.assert_has_awaits(
            [
                call("theme", None),
                call("use_rack_proxy", False),
            ]
        )
        services_mock.events.record_event.assert_has_awaits(
            [
                call(
                    event_type=EventTypeEnum.SETTINGS,
                    event_action=EVENT_DETAILS_MAP[
                        EventTypeEnum.SETTINGS
                    ].description,
                    event_description="Updated configuration setting 'theme' to 'None'.",
                    user_agent=ANY,
                    ip_address=IPv4Address("127.0.0.1"),
                    user="username",
                    endpoint=EndpointChoicesEnum.API,
                ),
                call(
                    event_type=EventTypeEnum.SETTINGS,
                    event_action=EVENT_DETAILS_MAP[
                        EventTypeEnum.SETTINGS
                    ].description,
                    event_description="Updated configuration setting 'use_rack_proxy' to 'False'.",
                    user_agent=ANY,
                    ip_address=IPv4Address("127.0.0.1"),
                    user="username",
                    endpoint=EndpointChoicesEnum.API,
                ),
            ]
        )

    async def test_set_configs_type_mismatch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
        )
        response = await client.put(
            self.BASE_PATH,
            json=jsonable_encoder(
                UpdateConfigurationsRequest(
                    configurations=[
                        UpdateConfigurationItemRequest(
                            name=PublicConfigName.THEME, value=[]
                        )
                    ]
                )
            ),
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422


@pytest.mark.asyncio
class TestConfigurationsApiRBAC:
    BASE_PATH = f"{V3_API_PREFIX}/configurations"

    async def test_get_configurations_unrestricted(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = "test"
        response = await mocked_api_client_user_rbac.get(
            f"{self.BASE_PATH}/{ThemeConfig.name}"
        )
        assert response.status_code == 200

    async def test_get_configurations_restricted_forbidden(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        response = await mocked_api_client_user_rbac.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}&name={UseRackProxyConfig.name}"
        )
        assert response.status_code == 403

    async def test_get_configurations_restricted_ok_admin(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac_admin: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            ThemeConfig.name: ThemeConfig.default,
            UseRackProxyConfig.name: UseRackProxyConfig.default,
        }
        response = await mocked_api_client_user_rbac_admin.get(
            f"{self.BASE_PATH}?name={ThemeConfig.name}&name={UseRackProxyConfig.name}"
        )
        assert response.status_code == 200

    async def test_get_configuration_unrestricted(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get.return_value = "test"
        response = await mocked_api_client_user_rbac.get(
            f"{self.BASE_PATH}/{ThemeConfig.name}"
        )
        assert response.status_code == 200

    async def test_get_configuration_restricted_forbidden(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        response = await mocked_api_client_user_rbac.get(
            f"{self.BASE_PATH}/{UseRackProxyConfig.name}"
        )
        assert response.status_code == 403

    async def test_get_configuration_restricted_ok_admin(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac_admin: AsyncClient,
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            ThemeConfig.name: ThemeConfig.default,
            UseRackProxyConfig.name: UseRackProxyConfig.default,
        }
        response = await mocked_api_client_user_rbac_admin.get(
            f"{self.BASE_PATH}/{UseRackProxyConfig.name}"
        )
        assert response.status_code == 200
