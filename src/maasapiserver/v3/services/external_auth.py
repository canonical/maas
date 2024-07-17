#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasapiserver.v3.services.secrets import SecretsService


class ExternalAuthService(Service):
    EXTERNAL_AUTH_SECRET_PATH = "global/external-auth"

    def __init__(
        self,
        connection: AsyncConnection,
        secrets_service: SecretsService,
    ):
        super().__init__(connection)
        self.secrets_service = secrets_service

    async def get_external_auth(self) -> ExternalAuthConfig | None:
        """
        Same logic of maasserver.middleware.ExternalAuthInfoMiddleware._get_external_auth_info
        """
        config = await self.secrets_service.get_composite_secret(
            path=self.EXTERNAL_AUTH_SECRET_PATH, default={}
        )
        candid_endpoint = config.get("url", "")
        rbac_endpoint = config.get("rbac-url", "")
        auth_domain = config.get("domain", "")
        auth_admin_group = config.get("admin-group", "")

        if rbac_endpoint:
            auth_type = ExternalAuthType.RBAC
            auth_endpoint = rbac_endpoint.rstrip("/") + "/auth"
            # not used, ensure they're unset
            auth_domain = ""
            auth_admin_group = ""
        elif candid_endpoint:
            auth_type = ExternalAuthType.CANDID
            auth_endpoint = candid_endpoint
        else:
            return None

        # strip trailing slashes as otherwise js-bakery ends up using double
        # slashes in the URL
        return ExternalAuthConfig(
            type=auth_type,
            url=auth_endpoint.rstrip("/"),
            domain=auth_domain,
            admin_group=auth_admin_group,
        )
