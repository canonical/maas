from datetime import datetime, timedelta, timezone

from hvac.exceptions import VaultError
import pytest

from maasserver import vault
from maasserver.vault import (
    _get_region_vault_client,
    get_region_vault_client,
    hvac,
    VaultClient,
    WrappedSecretError,
)


@pytest.fixture
def vault_client(mock_hvac_client):
    yield VaultClient(
        url="http://localhost:8200",
        role_id="123",
        secret_id="xyz",
        secrets_base_path="prefix",
        client=mock_hvac_client,
    )


class TestVaultClient:
    def test_set(self, mock_hvac_client):
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            client=mock_hvac_client,
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_hvac_client.mock_kv.store == {"prefix/mysecret": value}

    def test_set_custom_mount(self, mock_hvac_client):
        mock_hvac_client.mock_kv.expected_mount_point = "other/secret/mount"
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            secrets_mount="other/secret/mount",
            client=mock_hvac_client,
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_hvac_client.mock_kv.store == {"prefix/mysecret": value}

    def test_get(self, vault_client):
        value = {"foo": "bar"}
        vault_client.set("mysecret", value)
        assert vault_client.get("mysecret") == value

    def test_get_not_found(self, vault_client):
        with pytest.raises(hvac.exceptions.InvalidPath):
            vault_client.get("mysecret")

    def test_delete(self, mock_hvac_client):
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            client=mock_hvac_client,
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        client.delete("mysecret")
        assert mock_hvac_client.mock_kv.store == {}

    def test_auth_on_request(self, mock_hvac_client):
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            client=mock_hvac_client,
        )
        client.set("mysecret", {"foo": "bar"})
        mock_hvac_client.auth.approle.login.assert_called_once_with(
            role_id="123", secret_id="xyz"
        )
        client.set("othersecret", {"a": "b"})
        # authentication is not called again since token is still valid
        mock_hvac_client.auth.approle.login.assert_called_once()

    def test_reauth_on_request_if_token_expired(self, mock_hvac_client):
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            client=mock_hvac_client,
        )
        client.set("mysecret", {"foo": "bar"})
        assert len(mock_hvac_client.auth.approle.login.mock_calls) == 1
        # simulate having an expired token
        client._token_expire = datetime.now(tz=timezone.utc) - timedelta(
            minutes=10
        )
        client.set("othersecret", {"a": "b"})
        assert len(mock_hvac_client.auth.approle.login.mock_calls) == 2


@pytest.mark.django_db
class TestGetRegionVaultClient:
    def test_cached(self, mocker):
        mock_get_client = mocker.patch.object(
            vault, "_get_region_vault_client"
        )
        get_region_vault_client()
        get_region_vault_client()
        mock_get_client.assert_called_once()

    def test_no_client_if_not_all_configs(self, factory, vault_regionconfig):
        # the secret is not set
        vault_regionconfig["vault_url"] = "http://vault:8200"
        vault_regionconfig["vault_approle_id"] = "x-y-z"
        assert _get_region_vault_client() is None

    def test_get_client(self, factory, vault_regionconfig):
        approle_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        secrets_path = factory.make_name("secrets")
        secrets_mount = factory.make_name("mount")
        vault_regionconfig["vault_url"] = "http://vault:8200"
        vault_regionconfig["vault_approle_id"] = approle_id
        vault_regionconfig["vault_secret_id"] = secret_id
        vault_regionconfig["vault_secrets_path"] = secrets_path
        vault_regionconfig["vault_secrets_mount"] = secrets_mount
        client = _get_region_vault_client()
        assert isinstance(client, VaultClient)
        assert client._role_id == approle_id
        assert client._secret_id == secret_id
        assert client._secrets_base_path == secrets_path
        assert client._secrets_mount == secrets_mount

    def test_get_client_with_custom_secrets_mount(
        self, factory, vault_regionconfig
    ):
        approle_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        vault_regionconfig["vault_url"] = "http://vault:8200"
        vault_regionconfig["vault_approle_id"] = approle_id
        vault_regionconfig["vault_secret_id"] = secret_id
        vault_regionconfig["vault_secrets_mount"] = "other/secrets"
        client = _get_region_vault_client()
        assert client._secrets_mount == "other/secrets"


class TestUnwrapSecret:
    def test_unwrap_secret_success(self, factory, mocker, mock_hvac_client):
        secret_id = factory.make_name("uuid")
        mock_hvac_client.sys.unwrap.return_value = {
            "data": {"secret_id": secret_id}
        }
        assert vault.unwrap_secret("http://vault:8200", "token") == secret_id

    def test_unwrap_secret_no_secret_id_wrapped(
        self, mocker, mock_hvac_client
    ):
        mock_hvac_client.sys.unwrap.return_value = {
            "data": {"something_thats_not_secret_id": "is wrapped"}
        }
        with pytest.raises(WrappedSecretError):
            vault.unwrap_secret("http://vault:8200", "token")

    def test_unwrap_secret_no_data_wrapped(self, mocker, mock_hvac_client):
        mock_hvac_client.sys.unwrap.return_value = {
            "not data": {"something_thats_not_secret_id": "is wrapped"}
        }
        with pytest.raises(WrappedSecretError):
            vault.unwrap_secret("http://vault:8200", "token")

    def test_unwrap_secret_reraises_hvac_exceptions(
        self, mocker, mock_hvac_client
    ):
        mocker.patch.object(
            mock_hvac_client.sys, "unwrap"
        ).side_effect = VaultError("Test")
        with pytest.raises(VaultError):
            vault.unwrap_secret("http://vault:8200", "token")
