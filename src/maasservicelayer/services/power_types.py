#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.power_types import (
    AbstractPowerTypeRepository,
)
from maasservicelayer.services.base import Service


class PowerTypesService(Service):
    """Service for listing power types with FIPS annotations."""

    def __init__(
        self,
        context: Context,
        repository: AbstractPowerTypeRepository,
    ):
        super().__init__(context)
        self.repository = repository

    async def list(self) -> list[dict[str, Any]]:
        """Return all power types with FIPS classification fields."""
        return self.repository.list()
