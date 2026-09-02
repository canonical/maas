#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.auth.base import check_permissions
from maascommon.fips import get_fips_status
from maascommon.hardening import (
    CONF_KEYS,
    CONF_LIST_KEYS,
    is_hardening_enabled,
)
from maasserver.config import RegionConfiguration
from maasservicelayer.auth.jwt import UserRole
from provisioningserver.utils.version import get_running_version


class HardeningConfiguration(BaseModel):
    """The hardening parameters as managed by `maas config-hardening`."""

    api_tls_dhparam: str
    api_bind: list[str]
    api_bind6: list[str]
    prometheus_bind: str
    temporal_bind: str
    rpc_bind: list[str]
    agent_api_bind: list[str]
    agent_api_bind6: list[str]
    dns_bind: list[str]
    dns_bind6: list[str]
    syslog_bind: list[str]
    http_proxy_bind: list[str]
    http_proxy_bind6: list[str]
    database_sslmode: str
    database_sslcert: str
    database_sslkey: str
    database_sslrootcert: str


class SystemInfoResponse(BaseModel):
    fips_active: bool
    hardening_active: bool
    hardening_configuration: HardeningConfiguration
    version: str


def _read_hardening_conf() -> dict:
    """Read the regiond.conf-backed hardening parameters."""
    scalar_keys = CONF_KEYS - CONF_LIST_KEYS
    with RegionConfiguration.open() as cfg:
        values: dict = {key: list(getattr(cfg, key)) for key in CONF_LIST_KEYS}
        values.update({key: str(getattr(cfg, key)) for key in scalar_keys})
    return values


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
    ) -> SystemInfoResponse:
        fips_status = get_fips_status()
        version = await run_in_threadpool(get_running_version)
        conf = await run_in_threadpool(_read_hardening_conf)
        hardening_enabled = is_hardening_enabled()
        return SystemInfoResponse(
            fips_active=fips_status.enabled,
            hardening_active=hardening_enabled,
            hardening_configuration=HardeningConfiguration(
                **conf,
            ),
            version=version.short_version,
        )
