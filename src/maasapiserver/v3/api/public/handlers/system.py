#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends
from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.auth.base import check_permissions
from maascommon.fips import get_fips_status
from maascommon.hardening import is_hardening_enabled
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


class SystemInfoResponse(BaseModel):
    fips_active: bool
    hardening_active: bool
    version: str


class SystemHandler(Handler):
    """System information API handler."""

    TAGS = ["System"]

    @handler(
        path="/system/info",
        methods=["GET"],
        tags=TAGS,
        responses={200: {"model": SystemInfoResponse}},
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_system_info(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SystemInfoResponse:
        fips_status = get_fips_status()
        version = await services.configurations.get("maas_version")
        if version is None:
            raise RuntimeError(
                "maas_version configuration key is missing — "
                "MAAS may not have completed initialisation."
            )
        return SystemInfoResponse(
            fips_active=fips_status.enabled,
            hardening_active=is_hardening_enabled(),
            version=version,
        )
