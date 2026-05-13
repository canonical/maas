# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.builders.power_drivers import PowerDriverBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.power_drivers import (
    PowerDriversRepository,
)
from maasservicelayer.models.base import Unset
from maasservicelayer.models.power_drivers import DriverSchema, PowerDriver
from maasservicelayer.services.base import BaseService


class PowerDriversService(
    BaseService[PowerDriver, PowerDriversRepository, PowerDriverBuilder]
):
    """Service for managing rack-registered power drivers."""

    def __init__(
        self,
        context: Context,
        repository: PowerDriversRepository,
    ):
        super().__init__(context, repository)

    async def get_available_power_types(self) -> list[dict[str, Any]]:
        """Get merged set of available power types.

        Merges rack-registered drivers with builtin drivers (manual, webhook).
        Rack-registered drivers take precedence over builtins by name.
        """
        # Get all registered drivers from all racks
        all_drivers = await self.repository.list_all()

        # Build a dict keyed by driver_name (rack-registered takes precedence)
        drivers_by_name = {}
        for driver in all_drivers:
            name = driver.driver_name
            if name not in drivers_by_name:
                drivers_by_name[name] = driver.schema

        return list(drivers_by_name.values())

    async def pre_create_hook(self, builder: PowerDriverBuilder) -> None:
        """Validate schema before creating a driver registration."""
        schema_value = builder.schema
        if isinstance(schema_value, Unset):
            schema_dict = {}
        elif isinstance(schema_value, dict):
            schema_dict = schema_value
        else:
            schema_dict = schema_value.model_dump()
        # Validate against the DriverSchema contract
        DriverSchema(**schema_dict)
