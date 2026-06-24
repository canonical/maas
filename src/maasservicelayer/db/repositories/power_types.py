#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from typing import Any

from provisioningserver.drivers.power.fips import (
    DRIVER_FIPS_REGISTRY,
    DriverFIPSStatus,
)
from provisioningserver.drivers.power.registry import PowerDriverRegistry


# Intentional deviation from BaseRepository/ReadOnlyRepository: power types
# are sourced from the in-process driver registry (not the DB), so the
# standard repository contract does not apply.  A future migration to a DB
# table would replace this class with a proper ReadOnlyRepository subclass.
class AbstractPowerTypeRepository(ABC):
    """Read interface for power-type data."""

    @abstractmethod
    async def list(self) -> list[dict[str, Any]]:
        """Return all power types with FIPS classification fields."""


class PowerTypeRepository(AbstractPowerTypeRepository):
    """Reads power-type data from the in-process driver registry."""

    async def list(self) -> list[dict[str, Any]]:
        power_types = PowerDriverRegistry.get_schema(
            detect_missing_packages=False
        )
        result = []
        for pt in power_types:
            entry = dict(pt)
            name = entry.get("name", "")
            status, reason = DRIVER_FIPS_REGISTRY.get(
                name, (DriverFIPSStatus.COMPLIANT, None)
            )
            entry["fips_supported"] = status == DriverFIPSStatus.COMPLIANT
            entry["fips_unsupported_reason"] = reason
            result.append(entry)
        return result
