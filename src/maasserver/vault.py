from datetime import datetime, timedelta, timezone
from functools import cache
from textwrap import dedent
from typing import Any, NamedTuple, Optional

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


@cache
def get_region_vault_client() -> Optional[VaultClient]:
    """Return a VaultClient configured for the region controller, if configured.

    This is must be called once MAAS_UUID and Vault configuration (if any) are
    set, since the result is cached.  This is done since Vault configuration is
    not expected to change within the life of the region controller (a restart
    is needed).
    """
    return _get_region_vault_client()


def _get_region_vault_client() -> Optional[VaultClient]:
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


class AppRole(NamedTuple):
    """An approle with a secret."""

    name: str
    role_id: str
    secret_id: str


class VaultConfigurator:
    """Helper to configure Vault roles and approles for MAAS."""

    # policies for the "role manager" approle, which can manage roles for this MAAS
    ROLE_MANAGER_POLICY_HCL = dedent(
        """
        path "auth/approle/role/maas-{maas_uuid}-*" {{
          capabilities = ["read", "create", "update", "delete"]
        }}
        """
    )

    # policies for the "region controller" approle, which can manage secrets for
    # this MAAS
    REGION_POLICY_HCL = dedent(
        """
        path "{secrets_mount}/metadata/maas-{maas_uuid}/" {{
          capabilities = ["list"]
        }}
        path "{secrets_mount}/data/maas-{maas_uuid}/*" {{
          capabilities = ["read", "create", "update", "delete"]
        }}
        """
    )

    # common policies for the roles (to allow managing own tokens)
    COMMON_POLICY_HCL = dedent(
        """
        path "auth/token/lookup-self" {
          capabilities = ["read"]
        }
        path "auth/token/renew-self" {
          capabilities = ["update"]
        }
        """
    )

    TOKEN_TTL = "5m"

    def __init__(
        self,
        url: str,
        token: str,
        maas_uuid: str,
        secrets_mount: str = "secret",
    ):
        self._client = hvac.Client(url=url, token=token)
        self.maas_uuid = maas_uuid
        self.secrets_mount = secrets_mount

    @property
    def rolemanager_policy_name(self) -> str:
        return f"maas-{self.maas_uuid}-rolemanager"

    @property
    def region_policy_name(self) -> str:
        return f"maas-{self.maas_uuid}-region"

    def configure_policies(self):
        """Configure policies for this MAAS."""
        entries = (
            (self.rolemanager_policy_name, self.ROLE_MANAGER_POLICY_HCL),
            (self.region_policy_name, self.REGION_POLICY_HCL),
        )
        for name, policy_template in entries:
            policy_hcl = (
                policy_template.format(
                    maas_uuid=self.maas_uuid, secrets_mount=self.secrets_mount
                )
                + self.COMMON_POLICY_HCL
            ).strip()
            self._client.sys.create_or_update_policy(
                name=name, policy=policy_hcl
            )

    def get_approle_with_secret(
        self, policy: str, name_suffix: str = ""
    ) -> AppRole:
        """Create (or update) an approle with a specified policy.

        The name of the approle is built by appending the suffix to the policy
        name.
        """
        approle_cli = self._client.auth.approle
        role_name = policy
        if name_suffix:
            role_name += f"-{name_suffix}"
        approle_cli.create_or_update_approle(
            role_name=role_name,
            token_policies=[policy],
            token_ttl=self.TOKEN_TTL,
            token_max_ttl=self.TOKEN_TTL,
        )
        role_id = approle_cli.read_role_id(role_name=role_name)["data"][
            "role_id"
        ]
        secret_id = approle_cli.generate_secret_id(role_name=role_name)[
            "data"
        ]["secret_id"]
        return AppRole(name=role_name, role_id=role_id, secret_id=secret_id)
