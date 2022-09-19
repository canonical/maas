from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from dateutil.parser import isoparse
import hvac

from maasserver.config import RegionConfiguration
from provisioningserver.utils.env import MAAS_UUID

# refresh the token if the remaining life is less than this
TOKEN_BEFORE_EXPIRY_LIMIT = timedelta(seconds=10)


SecretValue = dict[str, Any]


class VaultClient:
    """Wrapper for the Vault client."""

    def __init__(
        self,
        url: str,
        secrets_base_path: str,
        role_id: str,
        secret_id: str,
        secrets_mount: str = "secret",
    ):
        self._client = hvac.Client(url=url)
        self._secrets_mount = secrets_mount
        self._secrets_base_path = secrets_base_path
        self._role_id = role_id
        self._secret_id = secret_id
        # ensure a token is created at the first request
        self._token_expire = self._utcnow()

    def set(self, path: str, value: SecretValue):
        self._ensure_auth()
        self._kv.create_or_update_secret(
            self._secret_path(path),
            value,
            mount_point=self._secrets_mount,
        )

    def get(self, path: str) -> SecretValue:
        self._ensure_auth()
        return self._kv.read_secret(
            self._secret_path(path),
            mount_point=self._secrets_mount,
        )["data"]["data"]

    def delete(self, path: str):
        self._ensure_auth()
        return self._kv.delete_latest_version_of_secret(
            self._secret_path(path),
            mount_point=self._secrets_mount,
        )

    @property
    def _kv(self):
        return self._client.secrets.kv.v2

    def _utcnow(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def _ensure_auth(self):
        if self._token_expire - TOKEN_BEFORE_EXPIRY_LIMIT >= self._utcnow():
            return

        self._client.auth.approle.login(
            role_id=self._role_id, secret_id=self._secret_id
        )
        token_info = self._client.auth.token.lookup_self()
        self._token_expire = isoparse(token_info["data"]["expire_time"])

    def _secret_path(self, path: str) -> str:
        return f"{self._secrets_base_path}/{path}"


def get_region_vault_client() -> Optional[VaultClient]:
    """Return a VaultClient configured for the region controller.

    If configuration options for Vault are not set, None is returned.
    """
    maas_uuid = MAAS_UUID.get()
    if not maas_uuid:
        return None

    with RegionConfiguration.open() as config:
        if not all(
            (config.vault_url, config.vault_approle_id, config.vault_secret_id)
        ):
            return None
        return VaultClient(
            url=config.vault_url,
            secrets_base_path=f"maas-{maas_uuid}",
            role_id=config.vault_approle_id,
            secret_id=config.vault_secret_id,
            secrets_mount=config.vault_secrets_mount,
        )
