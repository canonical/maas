from datetime import datetime, timedelta, timezone
from functools import cache, wraps
import logging
from typing import Any, Callable, NamedTuple, Optional
from urllib.parse import urlparse

from dateutil.parser import isoparse
from django.core.exceptions import ImproperlyConfigured
import hvac
import requests

from maasserver.config import RegionConfiguration

# refresh the token if the remaining life is less than this
TOKEN_BEFORE_EXPIRY_LIMIT = timedelta(seconds=10)


SecretValue = dict[str, Any]


class VaultError(Exception):
    """Raised to wrap the hvac.exception.VaultError one."""


class UnknownSecretPath(Exception):
    """Raised when the path for a secret is unknown."""


class WrappedSecretError(Exception):
    """Raised when the provided token could not be used to obtain secret_id by unwrapping"""


def wrap_errors(func: Callable) -> Callable:
    """Wrap hvac exceptions with local ones."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            logging.exception(e)
            raise VaultError("Vault connection failed") from e
        except hvac.exceptions.VaultError as e:
            raise VaultError("Vault request failed") from e

    return wrapper


def _create_hvac_client(url: str, **kwargs) -> hvac.Client:
    """Create HVAC client for the given URL, with no proxies set."""
    # FIXME: This is gross, and unfortunately necessary due to
    # bootsources.get_simplestreams_env and
    # https://github.com/psf/requests/issues/2018
    # LP:2002528
    kwargs["proxies"] = {urlparse(url).scheme: None}
    return hvac.Client(url=url, **kwargs)


@wrap_errors
def unwrap_secret(url: str, wrapped_token: str) -> str:
    """Helper function to unwrap approle secret id from wrapped token"""
    client = _create_hvac_client(url, token=wrapped_token)
    try:
        return client.sys.unwrap()["data"]["secret_id"]
    except KeyError:
        raise WrappedSecretError(  # noqa: B904
            "Unable to unwrap Secret ID with given token."
        )


class VaultClient:
    """Wrapper for the Vault client."""

    def __init__(
        self,
        url: str,
        role_id: str,
        secret_id: str,
        secrets_base_path: str,
        secrets_mount: str = "secret",
        client: Optional[hvac.Client] = None,
    ):
        self._client = client or _create_hvac_client(url)
        self._secrets_mount = secrets_mount
        self._secrets_base_path = secrets_base_path
        self._role_id = role_id
        self._secret_id = secret_id
        # ensure a token is created at the first request
        self._token_expire = self._utcnow()

    @wrap_errors
    def set(self, path: str, value: SecretValue):
        self._ensure_auth()
        self._kv.create_or_update_secret(
            self._secret_path(path),
            value,
            mount_point=self._secrets_mount,
        )

    @wrap_errors
    def get(self, path: str) -> SecretValue:
        self._ensure_auth()
        try:
            return self._kv.read_secret(
                self._secret_path(path),
                mount_point=self._secrets_mount,
            )["data"]["data"]
        except hvac.exceptions.InvalidPath:
            raise UnknownSecretPath(path)  # noqa: B904

    @wrap_errors
    def delete(self, path: str):
        self._ensure_auth()
        return self._kv.delete_metadata_and_all_versions(
            self._secret_path(path),
            mount_point=self._secrets_mount,
        )

    @wrap_errors
    def check_authentication(self):
        """Checks if vault is available, throws otherwise"""
        self._ensure_auth(force=True)

    @property
    def _kv(self):
        return self._client.secrets.kv.v2

    def _utcnow(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def _ensure_auth(self, force=False):
        if (
            not force
            and self._token_expire - TOKEN_BEFORE_EXPIRY_LIMIT
            >= self._utcnow()
        ):
            return

        self._client.auth.approle.login(
            role_id=self._role_id, secret_id=self._secret_id
        )
        token_info = self._client.auth.token.lookup_self()
        self._token_expire = isoparse(token_info["data"]["expire_time"])

    def _secret_path(self, path: str) -> str:
        return f"{self._secrets_base_path}/{path}"


class AppRole(NamedTuple):
    """An approle with a secret."""

    name: str
    role_id: str
    secret_id: str


@cache
def get_region_vault_client_if_enabled() -> Optional[VaultClient]:
    """Return a VaultClient configured for the region controller
    (if Vault is configured and enabled cluster-wide).

    This method exists because not all `get_region_vault_client` calls
    are from contexts where it's possible to check the DB flag. Since
    the Vault configuration is still expected to remain static until region restart,
    we can cache the flag value too to minimize DB queries amount."""
    from maasserver.models import Config

    if Config.objects.get_config("vault_enabled", False):
        client = get_region_vault_client()
        if not client:
            raise ImproperlyConfigured(
                "Vault is enabled cluster-wide, but is not configured for this region."
            )
        return client
    # Since Vault is disabled, there is no client to return
    return None


@cache
def get_region_vault_client() -> Optional[VaultClient]:
    """Return a VaultClient configured for the region controller, if configured.

    This is must be called once the Vault configuration (if any) is set, since
    the result is cached.  This is done since Vault configuration is not
    expected to change within the life of the region controller (a restart is
    needed).

    """
    return _get_region_vault_client()


def _get_region_vault_client() -> Optional[VaultClient]:
    """Return a VaultClient configured for the region controller.

    If configuration options for Vault are not set, None is returned.
    """
    with RegionConfiguration.open() as config:
        if not all(
            (config.vault_url, config.vault_approle_id, config.vault_secret_id)
        ):
            return None
        return VaultClient(
            url=config.vault_url,
            role_id=config.vault_approle_id,
            secret_id=config.vault_secret_id,
            secrets_base_path=config.vault_secrets_path,
            secrets_mount=config.vault_secrets_mount,
        )


def check_approle_permissions(
    url: str,
    role_id: str,
    secret_id: str,
    secrets_path: str,
    secrets_mount: str,
) -> None:
    """Tests permissions for the AppRole by performing basic actions."""
    client = VaultClient(
        url=url,
        role_id=role_id,
        secret_id=secret_id,
        secrets_base_path=secrets_path,
        secrets_mount=secrets_mount,
    )

    test_path = f"test-{role_id}"
    # Test create/update
    client.set(test_path, {"value": role_id})
    # Test read
    client.get(test_path)
    # Test delete
    client.delete(test_path)


def prepare_wrapped_approle(
    url: str,
    role_id: str,
    wrapped_token: str,
    secrets_path: str,
    secrets_mount: str,
) -> str:
    """Unwraps secret id, checks if the approle has enough permissions and returns the unwrapped secret_id"""
    secret_id = unwrap_secret(url, wrapped_token)
    check_approle_permissions(
        url=url,
        role_id=role_id,
        secret_id=secret_id,
        secrets_path=secrets_path,
        secrets_mount=secrets_mount,
    )
    return secret_id


def configure_region_with_vault(
    url: str,
    role_id: str,
    wrapped_token: str,
    secrets_path: str,
    secrets_mount: str,
):
    """Configure the region to use Vault.

    The AppRole Role ID and unwrapped Secret ID are stored in region configuration after permission validation.
    """
    secret_id = prepare_wrapped_approle(
        url=url,
        role_id=role_id,
        wrapped_token=wrapped_token,
        secrets_path=secrets_path,
        secrets_mount=secrets_mount,
    )

    with RegionConfiguration.open_for_update() as config:
        config.vault_url = url
        config.vault_approle_id = role_id
        config.vault_secret_id = secret_id
        config.vault_secrets_path = secrets_path
        config.vault_secrets_mount = secrets_mount
    # ensure future calls to get the client use the updated config
    clear_vault_client_caches()


def clear_vault_client_caches():
    """Clears cached vault clients, useful after reconfiguration"""
    get_region_vault_client.cache_clear()
    get_region_vault_client_if_enabled.cache_clear()
