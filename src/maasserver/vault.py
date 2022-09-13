from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil.parser import isoparse
import hvac

# refresh the token if the remaining life is less than this
TOKEN_BEFORE_EXPIRY_LIMIT = timedelta(seconds=10)


SecretValue = dict[str, Any]


class VaultClient:
    """Wrapper for the Vault client."""

    def __init__(
        self, url: str, secrets_base_path: str, role_id: str, secret_id: str
    ):
        self._client = hvac.Client(url=url)
        self._secrets_base_path = secrets_base_path
        self._role_id = role_id
        self._secret_id = secret_id
        # ensure a token is created at the first request
        self._token_expire = self._utcnow()

    def set(self, path: str, value: SecretValue):
        self._ensure_auth()
        return self._kv.create_or_update_secret(self._secret_path(path), value)

    def get(self, path: str) -> SecretValue:
        self._ensure_auth()
        return self._kv.read_secret(self._secret_path(path))["data"]["data"]

    def delete(self, path: str):
        self._ensure_auth()
        return self._kv.delete_latest_version_of_secret(
            self._secret_path(path)
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
