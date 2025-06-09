# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from enum import Enum

from fastapi import Query
from pydantic import BaseModel, Field

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
