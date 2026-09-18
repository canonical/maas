#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.auth.base import (
    check_authentication,
    get_authenticated_user,
)
from maascommon.fips import get_fips_status
from maascommon.hardening import is_hardening_enabled
from maasservicelayer.models.auth import AuthenticatedUser
from provisioningserver.utils.version import get_running_version


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
        dependencies=[Depends(check_authentication())],
    )
    async def get_system_info(
        self,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> SystemInfoResponse:
        assert authenticated_user is not None
        fips_status = get_fips_status()
        version = await run_in_threadpool(get_running_version)
        hardening_enabled = is_hardening_enabled()

        return SystemInfoResponse(
            fips_active=fips_status.enabled,
            hardening_active=hardening_enabled,
            version=version.short_version,
        )
