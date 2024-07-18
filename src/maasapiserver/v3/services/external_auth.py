#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import os

from macaroonbakery import bakery
from macaroonbakery.bakery._store import RootKeyStore
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasapiserver.v3.db.external_auth import ExternalAuthRepository
from maasapiserver.v3.services.secrets import SecretsService
from provisioningserver.security import to_bin, to_hex


# We need to implement RootKeyStore because we pass this service to the Macaroon Auth Checker
class ExternalAuthService(Service, RootKeyStore):

    EXTERNAL_AUTH_SECRET_PATH = "global/external-auth"
    BAKERY_KEY_SECRET_PATH = "global/macaroon-key"
    ROOTKEY_MATERIAL_SECRET_FORMAT = "rootkey/%s/material"

    # size in bytes of the key
    KEY_LENGTH = 24

    def __init__(
        self,
        connection: AsyncConnection,
        secrets_service: SecretsService,
        external_auth_repository: ExternalAuthRepository | None = None,
    ):
        super().__init__(connection)
        self.secrets_service = secrets_service
        self.external_auth_repository = (
            external_auth_repository or ExternalAuthRepository(connection)
        )

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

    async def get_or_create_bakery_key(self) -> bakery.PrivateKey:
        key = await self.secrets_service.get_simple_secret(
            path=self.BAKERY_KEY_SECRET_PATH, default=None
        )
        if key:
            return bakery.PrivateKey.deserialize(key)

        key = bakery.generate_key()
        await self.secrets_service.set_simple_secret(
            path=self.BAKERY_KEY_SECRET_PATH,
            value=key.serialize().decode("ascii"),
        )
        return key

    async def get(self, id: bytes) -> bytes | None:
        """Return the key with the specified bytes string id."""
        key = await self.external_auth_repository.find_by_id(id=int(id))
        if not key:
            return None
        if key.expiration < utcnow():
            await self._delete(id=key.id)
            return None
        return await self._get_key_material(id=key.id)

    async def root_key(self):
        key = await self.external_auth_repository.find_best_key()
        if not key:
            # delete expired keys (if any)
            expired_keys = (
                await self.external_auth_repository.find_expired_keys()
            )
            for expired_key in expired_keys:
                await self._delete(id=expired_key.id)
            key = await self._new_key()
        material = await self._get_key_material(id=key.id)
        return material, str(key.id).encode("ascii")

    async def _get_key_material(self, id: int) -> bytes | None:
        secret = await self.secrets_service.get_simple_secret(
            path=self.ROOTKEY_MATERIAL_SECRET_FORMAT % id, default=None
        )
        if not secret:
            return None
        return to_bin(secret)

    async def _new_key(self):
        key = await self.external_auth_repository.create()
        material = os.urandom(self.KEY_LENGTH)
        await self.secrets_service.set_simple_secret(
            path=self.ROOTKEY_MATERIAL_SECRET_FORMAT % key.id,
            value=to_hex(material),
        )
        return key

    async def _delete(self, id: int) -> None:
        """
        Delete the key and the related material
        """
        await self.external_auth_repository.delete(id=id)
        await self.secrets_service.delete(
            path=self.ROOTKEY_MATERIAL_SECRET_FORMAT % id
        )
