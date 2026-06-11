# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Power types list endpoint with FIPS compliance annotations."""

from fastapi import Depends
from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    UnauthorizedBodyResponse,
)
from maasapiserver.v3.auth.base import (
    check_authentication,
    get_authenticated_user,
)
from maasservicelayer.models.auth import AuthenticatedUser
from provisioningserver.drivers.power.fips import (
    DRIVER_FIPS_REGISTRY,
    DriverFIPSStatus,
)
from provisioningserver.drivers.power.registry import PowerDriverRegistry


class PowerTypeWithFIPSResponse(BaseModel):
    """A single power driver type entry with FIPS compliance information."""

    name: str
    description: str
    fips_supported: bool
    fips_unsupported_reason: str | None = None


class PowerTypesListResponse(BaseModel):
    """Response body for GET /power-types."""

    power_types: list[PowerTypeWithFIPSResponse]


def _get_power_types_with_fips() -> list[PowerTypeWithFIPSResponse]:
    """Build the annotated power-type list from the driver registry.

    Each entry carries ``fips_supported`` and, when the driver is not
    supported in FIPS mode, ``fips_unsupported_reason`` drawn from
    ``DRIVER_FIPS_REGISTRY``.
    """
    result: list[PowerTypeWithFIPSResponse] = []
    for _, driver in PowerDriverRegistry:
        fips_entry = DRIVER_FIPS_REGISTRY.get(driver.name)
        if fips_entry is not None:
            fips_status, reason = fips_entry
            fips_supported = (
                fips_status != DriverFIPSStatus.UNSUPPORTED_IN_FIPS
            )
            fips_unsupported_reason = reason if not fips_supported else None
        else:
            # Drivers not in the registry are treated as FIPS-unsupported
            # (fail-closed: unknown drivers are not trusted).
            fips_supported = False
            fips_unsupported_reason = "Driver not listed in FIPS registry"

        result.append(
            PowerTypeWithFIPSResponse(
                name=driver.name,
                description=driver.description,
                fips_supported=fips_supported,
                fips_unsupported_reason=fips_unsupported_reason,
            )
        )

    return sorted(result, key=lambda d: d.name)


class PowerTypesHandler(Handler):
    """Power types list API handler."""

    TAGS = ["Power types"]

    @handler(
        path="/power-types",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": PowerTypesListResponse},
            401: {"model": UnauthorizedBodyResponse},
        },
        status_code=200,
        dependencies=[Depends(check_authentication())],
    )
    async def list_power_types(
        self,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> PowerTypesListResponse:
        """Return all available power driver types with FIPS compliance info.

        Each entry indicates whether the driver is supported when MAAS is
        running on a FIPS-enabled host and, if not, the reason why.
        """
        return PowerTypesListResponse(power_types=_get_power_types_with_fips())
