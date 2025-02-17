#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.configurations import (
    ConfigurationsRepository,
)
from maasservicelayer.services.base import Service


class ConfigurationsService(Service):
    def __init__(
        self,
        context: Context,
        configurations_repository: ConfigurationsRepository,
    ):
        super().__init__(context)
        self.configurations_repository = configurations_repository

    # We inherit this from the django legacy implementation. When we will have moved away, we can refactor the way we store the
    # configurations and provide a proper typing. For the time being, the consumer has to know how to consume the configuration.
    async def get(self, name: str, default=None) -> Any:
        configuration = await self.configurations_repository.get(name)
        # TODO: get the value from the default config (src/maasserver/models/config.py)
        # if the value is not in the db.
        if not configuration:
            return default
        return configuration.value
