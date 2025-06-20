# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import suppress
from typing import Any, TypeVar

import structlog

from maasservicelayer.builders.configurations import (
    DatabaseConfigurationBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.database_configurations import (
    DatabaseConfigurationsClauseFactory,
)
from maasservicelayer.models.configurations import (
    Config,
    ConfigFactory,
    UUIDConfig,
)
from maasservicelayer.services.base import Service
from maasservicelayer.services.database_configurations import (
    DatabaseConfigurationNotFound,
    DatabaseConfigurationsService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.secrets import SecretNotFound, SecretsService
from provisioningserver.utils.version import get_running_version

T = TypeVar("T", bound=Config)

logger = structlog.getLogger()


class ConfigurationsService(Service):
    """
    Service providing unified access to configuration values.

    This service retrieves configuration values from either a database or a
    secrets backend (such as Vault). It acts as a high-level abstraction layer
    to access configurations, some of which may be defined in
    `maasservicelayer.models.configurations`, while others may be dynamically
    stored in the backend.

    It is also designed to be used by the Django application, and may return
    raw values (not strictly instances of `Config`), allowing flexible usage
    even for configurations not explicitly modeled.
    """

    def __init__(
        self,
        context: Context,
        database_configurations_service: DatabaseConfigurationsService,
        secrets_service: SecretsService,
        events_service: EventsService,
    ):
        super().__init__(context)
        self.database_configurations_service = database_configurations_service
        self.secrets_service = secrets_service
        self.events_service = events_service

    async def get(self, name: str, default=None) -> Any:
        """
        Retrieve a single configuration value.

        Looks up the configuration by name. If the configuration is defined
        and stored as a secret, it is retrieved from the secrets backend.
        Otherwise, it is fetched from the database.

        If the configuration is unknown or not found, the provided `default`
        value is returned (or `None` if not specified).

        Args:
            name: The name of the configuration to retrieve.
            default: The default value to return if the configuration is
                missing or undefined.

        Returns:
            The configuration value, or `default` if not found.
        """
        config_model = None
        try:
            config_model = ConfigFactory.get_config_model(name)
        except ValueError:
            logger.warn(
                f"The configuration '{name}' is not known. Using the default {default} if the config does not exist in the DB."
            )
            default_value = default
        else:
            default_value = config_model.default
        try:
            if config_model and config_model.stored_as_secret:
                assert config_model.secret_model is not None
                return await self.secrets_service.get_simple_secret(
                    config_model.secret_model
                )
            return await self.database_configurations_service.get(name=name)
        except (DatabaseConfigurationNotFound, SecretNotFound):
            return default_value

    async def get_many(self, names: set[str]) -> dict[str, Any]:
        """
        Retrieve multiple configuration values at once.

        Secret-stored configurations are fetched from the secrets
        backend; the rest are fetched from the database.

        If a configuration is unknown or not found, its default is returned.

        Args:
            names: A set of configuration names to retrieve.

        Returns:
            A dictionary mapping configuration names to their resolved values.
        """

        config_models = {
            name: ConfigFactory.get_config_model(name)
            for name in names
            if name in ConfigFactory.ALL_CONFIGS
        }

        # Build a first result with all the default values, then look in the secrets/configs in the db for overrides.
        configs = {
            name: config_model.default
            for name, config_model in config_models.items()
        }

        # What configs we should lookup from the DB
        regular_configs = set(names)

        # secrets configs
        for name, model in config_models.items():
            if model.stored_as_secret:
                with suppress(SecretNotFound):
                    assert model.secret_model is not None
                    configs[
                        name
                    ] = await self.secrets_service.get_simple_secret(
                        model.secret_model
                    )
                    # The config was found and added to the result: remove it from the regular config.
                    regular_configs.remove(name)

        # Lookup the remaining configs from the DB.
        configs.update(
            await self.database_configurations_service.get_many(
                query=QuerySpec(
                    DatabaseConfigurationsClauseFactory.with_names(
                        regular_configs
                    )
                )
            )
        )
        return configs

    async def set(self, name: str, value: Any) -> None:
        config_model = None
        try:
            config_model = ConfigFactory.get_config_model(name)
        except ValueError:
            logger.warn(
                f"The configuration '{name}' is not known. Anyways, it's going to be stored in the DB."
            )
        if config_model and config_model.stored_as_secret:
            await self.secrets_service.set_simple_secret(
                config_model.secret_model,  # pyright: ignore[reportArgumentType]
                value,
            )
        else:
            await self.database_configurations_service.create_or_update(
                DatabaseConfigurationBuilder(name=name, value=value)
            )

    async def get_maas_user_agent(self):
        # TODO: move get_running_version to maascommon.
        version = get_running_version()
        user_agent = f"maas/{version.short_version}/{version.extended_info}"
        uuid = await self.get(UUIDConfig.name)
        if uuid:
            user_agent += f"/{uuid}"
        return user_agent
