# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any
from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.database_configurations import (
    DatabaseConfigurationsClauseFactory,
)
from maasservicelayer.models.configurations import (
    MAASProxyPortConfig,
    RPCSharedSecretConfig,
    ThemeConfig,
    VCenterPasswordConfig,
)
from maasservicelayer.models.secrets import VCenterPasswordSecret
from maasservicelayer.services import (
    ConfigurationsService,
    EventsService,
    SecretsService,
    ServiceCollectionV3,
)
from maasservicelayer.services.database_configurations import (
    DatabaseConfigurationNotFound,
    DatabaseConfigurationsService,
)
from maasservicelayer.services.secrets import SecretNotFound
from tests.fixtures.factories.configuration import create_test_configuration
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestIntegrationConfigurationsService:
    @pytest.mark.parametrize(
        "config, default_value",
        [
            ("theme", ""),
            ("maas_proxy_port", 8000),
            ("prefer_v4_proxy", False),
            ("upstream_dns", None),
            ("maas_internal_domain", "maas-internal"),
        ],
    )
    async def test_get(
        self, config: str, default_value: Any, services: ServiceCollectionV3
    ):
        assert (await services.configurations.get(config)) == default_value

    async def test_get_with_default_value(self, services: ServiceCollectionV3):
        # For known configurations the default value in the argument is ignored and it's taken the default value for the
        # configuration model instead.
        # This is for backwards compatibility given that we want to use the service layer also for the configurations in
        # django. Once django is removed, we can also refactor this and raise a proper exception in case.
        assert (await services.configurations.get("theme", None)) == ""

    async def test_get_with_default_value_unkwnown_config(
        self, services: ServiceCollectionV3
    ):
        assert (
            await services.configurations.get("unknown_config", "value")
        ) == "value"

    async def test_get_config_stored_in_database(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_test_configuration(
            fixture, name="myconfiguration", value="myvalue"
        )
        assert (
            await services.configurations.get("myconfiguration")
        ) == "myvalue"

    async def test_get_config_stored_as_secret(
        self, services: ServiceCollectionV3
    ):
        await services.secrets.set_simple_secret(
            VCenterPasswordSecret(), "mypassword"
        )
        assert (
            await services.configurations.get("vcenter_password")
        ) == "mypassword"

    async def test_get_config_stored_as_secret_with_default(
        self, services: ServiceCollectionV3
    ):
        assert (await services.configurations.get("vcenter_password")) == ""

    async def test_get_many(self, services: ServiceCollectionV3):
        expected_configs = {
            "theme": "",
            "maas_proxy_port": 8000,
            "prefer_v4_proxy": False,
        }
        assert (
            await services.configurations.get_many(
                set(expected_configs.keys())
            )
        ) == expected_configs

    async def test_get_many_stored_in_database(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        expected_configs = {"theme": "", "myconfiguration": "myvalue"}
        await create_test_configuration(
            fixture, name="myconfiguration", value="myvalue"
        )
        assert (
            await services.configurations.get_many(
                set(expected_configs.keys())
            )
        ) == expected_configs

    async def test_get_many_stored_as_secret(
        self, services: ServiceCollectionV3
    ):
        expected_configs = {
            "theme": "",
            "vcenter_password": "mypassword",
            "rpc_shared_secret": None,
        }
        await services.secrets.set_simple_secret(
            VCenterPasswordSecret(), "mypassword"
        )
        assert (
            await services.configurations.get_many(
                set(expected_configs.keys())
            )
        ) == expected_configs


@pytest.mark.asyncio
class TestConfigurationsService:
    async def test_get_from_database(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        service.database_configurations_service.get.return_value = "myvalue"
        assert (await service.get(ThemeConfig.name)) == "myvalue"
        service.database_configurations_service.get.assert_called_once_with(
            name=ThemeConfig.name
        )

    async def test_get_from_database_not_found_returns_default(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        service.database_configurations_service.get.side_effect = (
            DatabaseConfigurationNotFound(ThemeConfig.name)
        )
        assert (await service.get(ThemeConfig.name)) == ""
        service.database_configurations_service.get.assert_called_once_with(
            name=ThemeConfig.name
        )

    async def test_get_from_secrets(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        service.secrets_service.get_simple_secret.return_value = "mypassword"
        assert (await service.get(VCenterPasswordConfig.name)) == "mypassword"
        service.secrets_service.get_simple_secret.assert_called_once_with(
            VCenterPasswordConfig.secret_model
        )
        service.database_configurations_service.get.assert_not_called()

    async def test_get_from_secrets_returns_default(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        service.secrets_service.get_simple_secret.side_effect = SecretNotFound(
            VCenterPasswordConfig.secret_model.secret_name
        )
        assert (await service.get(VCenterPasswordConfig.name)) == ""
        service.secrets_service.get_simple_secret.assert_called_once_with(
            VCenterPasswordConfig.secret_model
        )
        service.database_configurations_service.get.assert_not_called()

    async def test_get_many_from_database(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        expected_configs = {
            ThemeConfig.name: "mytheme",
            MAASProxyPortConfig.name: 1234,
        }
        service.database_configurations_service.get_many.return_value = (
            expected_configs
        )

        assert (
            await service.get_many(
                {ThemeConfig.name, MAASProxyPortConfig.name}
            )
        ) == expected_configs
        service.database_configurations_service.get_many.assert_called_once()

    async def test_get_many_from_secrets(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        expected_configs = {
            VCenterPasswordConfig.name: "mypassword",
            RPCSharedSecretConfig.name: "secret",
        }
        service.secrets_service.get_simple_secret.side_effect = (
            lambda key: "mypassword"
            if isinstance(key, VCenterPasswordSecret)
            else "secret"
        )
        service.database_configurations_service.get_many.return_value = {}
        assert (
            await service.get_many(
                {VCenterPasswordConfig.name, RPCSharedSecretConfig.name}
            )
        ) == expected_configs
        assert service.secrets_service.get_simple_secret.call_count == 2

    async def test_get_from_database_and_secrets(self):
        service = ConfigurationsService(
            context=Context(),
            database_configurations_service=Mock(
                DatabaseConfigurationsService
            ),
            secrets_service=Mock(SecretsService),
            events_service=Mock(EventsService),
        )
        service.database_configurations_service.get_many.return_value = {
            ThemeConfig.name: "mytheme"
        }
        service.secrets_service.get_simple_secret.return_value = "mypassword"
        assert (
            await service.get_many(
                {ThemeConfig.name, VCenterPasswordConfig.name}
            )
        ) == {
            ThemeConfig.name: "mytheme",
            VCenterPasswordConfig.name: "mypassword",
        }

        service.secrets_service.get_simple_secret.assert_called_once_with(
            VCenterPasswordConfig.secret_model
        )
        service.database_configurations_service.get_many.assert_called_once_with(
            query=QuerySpec(
                DatabaseConfigurationsClauseFactory.with_names(
                    [ThemeConfig.name]
                )
            )
        )
