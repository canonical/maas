from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from maasserver import vault
from maasserver.config import RegionConfiguration
from maasserver.vault import get_region_vault_client, hvac, VaultClient
from provisioningserver.utils.env import MAAS_UUID


class MockKVStore:

    expected_mount_point = "secret"

    def __init__(self):
        self.store = {}

    def create_or_update_secret(self, path, value, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        self.store[path] = value

    def read_secret(self, path, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        try:
            # include only relevant fields in response
            return {"data": {"data": self.store[path]}}
        except KeyError:
            raise hvac.exceptions.InvalidPath(
                url=f"http://localhost:8200/v1/secret/data/{path}",
                method="get",
            )

    def delete_latest_version_of_secret(self, path, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        self.store.pop(path, None)


@pytest.fixture
def mock_kv():
    yield MockKVStore()


@pytest.fixture
def mock_hvac(mocker, mock_kv):
    token_expiry = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
    expire_time = token_expiry.isoformat().replace("+00:00", "000Z")
    cli = mocker.patch.object(hvac, "Client").return_value
    cli.auth.token.lookup_self = lambda: {"data": {"expire_time": expire_time}}
    cli.secrets.kv.v2 = mock_kv
    yield cli


@pytest.mark.usefixtures("mock_hvac")
class TestVaultClient:
    def test_set(self, mock_kv):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_kv.store == {"prefix/mysecret": value}

    def test_set_custom_mount(self, mock_kv):
        mock_kv.expected_mount_point = "other/secret/mount"
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
            secrets_mount="other/secret/mount",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_kv.store == {"prefix/mysecret": value}

    def test_get(self):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert client.get("mysecret") == value

    def test_get_not_found(self):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        with pytest.raises(hvac.exceptions.InvalidPath):
            client.get("mysecret")

    def test_delete(self, mock_kv):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        client.delete("mysecret")
        assert mock_kv.store == {}

    def test_auth_on_request(self, mock_hvac):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        client.set("mysecret", {"foo": "bar"})
        mock_hvac.auth.approle.login.assert_called_once_with(
            role_id="123", secret_id="xyz"
        )
        client.set("othersecret", {"a": "b"})
        # authentication is not called again since token is still valid
        mock_hvac.auth.approle.login.assert_called_once()

    def test_reauth_on_request_if_token_expired(self, mock_hvac):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        client.set("mysecret", {"foo": "bar"})
        assert len(mock_hvac.auth.approle.login.mock_calls) == 1
        # simulate having an expired token
        client._token_expire = datetime.now(tz=timezone.utc) - timedelta(
            minutes=10
        )
        client.set("othersecret", {"a": "b"})
        assert len(mock_hvac.auth.approle.login.mock_calls) == 2


@pytest.fixture
def mock_regionconfig(mocker):
    store = {}

    @contextmanager
    def config_ctx():
        yield RegionConfiguration(store)

    mocker.patch.object(vault.RegionConfiguration, "open", config_ctx)
    yield store


@pytest.mark.django_db
class TestGetRegionVaultClient:
    def test_no_client_if_no_maas_uuid(self, mock_regionconfig):
        MAAS_UUID.set(None)
        assert get_region_vault_client() is None

    def test_no_client_if_not_all_configs(self, factory, mock_regionconfig):
        MAAS_UUID.set(factory.make_name("uuid"))
        # the secret is not set
        mock_regionconfig["vault_url"] = "http://vault:8200"
        mock_regionconfig["vault_approle_id"] = "x-y-z"
        assert get_region_vault_client() is None

    def test_get_client(self, factory, mock_regionconfig):
        MAAS_UUID.set(factory.make_name("uuid"))
        approle_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        mock_regionconfig["vault_url"] = "http://vault:8200"
        mock_regionconfig["vault_approle_id"] = approle_id
        mock_regionconfig["vault_secret_id"] = secret_id
        client = get_region_vault_client()
        assert isinstance(client, VaultClient)
        assert client._role_id == approle_id
        assert client._secret_id == secret_id

    def test_get_client_with_custom_secrets_mount(
        self, factory, mock_regionconfig
    ):
        MAAS_UUID.set(factory.make_name("uuid"))
        approle_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        mock_regionconfig["vault_url"] = "http://vault:8200"
        mock_regionconfig["vault_approle_id"] = approle_id
        mock_regionconfig["vault_secret_id"] = secret_id
        mock_regionconfig["vault_secrets_mount"] = "other/secrets"
        client = get_region_vault_client()
        assert client._secrets_mount == "other/secrets"
