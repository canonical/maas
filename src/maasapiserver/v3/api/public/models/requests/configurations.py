# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
from typing import Any

from fastapi import Query
from pydantic import BaseModel, Field, ValidationError

from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.configurations import ConfigFactory

# Beautify openapi.
PublicConfigName = Enum(
    "PublicConfigName",
    {key.upper(): key for key in ConfigFactory.PUBLIC_CONFIGS.keys()},
)


class ConfigurationsFiltersParams(BaseModel):
    names: set[PublicConfigName] = Field(  # pyright: ignore [reportInvalidTypeForm]
        Query(
            default=set(),
            title="Filter by configuration name",
            description="A set of configuration names to filter by.",
            alias="name",
        )
    )

    def get_names(self) -> set[str]:
        return {name.value for name in self.names}


class UpdateConfigurationRequest(BaseModel):
    value: Any = Field(description="The value of the configuration.")

    def check_typing(self, name: str):
        model = ConfigFactory.get_config_model(name)
        try:
            model(value=self.value)
        except ValidationError as e:
            raise ValidationException.build_for_field(
                field="value",
                message=f"Expected type '{model.__fields__['value'].type_.__name__}' but got '{type(self.value).__name__}' for configuration '{name}'",
            ) from e


class UpdateConfigurationItemRequest(UpdateConfigurationRequest):
    name: PublicConfigName = Field(  # pyright: ignore [reportInvalidTypeForm]
        description="The name of the configuration."
    )

    def check_config_typing(self):
        super().check_typing(self.name.value)


class UpdateConfigurationsRequest(BaseModel):
    configurations: list[UpdateConfigurationItemRequest] = Field(
        description="List of configurations to be updated."
    )

    def check_typing(self):
        for configuration in self.configurations:
            configuration.check_config_typing()
