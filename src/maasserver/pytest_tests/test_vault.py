from datetime import datetime, timedelta, timezone
from unittest.mock import ANY

from hvac.exceptions import VaultError
import pytest

from maasserver import vault
from maasserver.models import Config
from maasserver.vault import (
    _get_region_vault_client,
    get_region_vault_client,
    get_region_vault_client_if_enabled,
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

    def test_check_authentication_ensures_auth(self, mocker, mock_hvac_client):
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            client=mock_hvac_client,
        )
        ensure_auth = mocker.patch.object(client, "_ensure_auth")
        client.check_authentication()
        ensure_auth.assert_called_once()

    def test_check_authentication_reraises_ensure_auth_errors(
        self, mocker, mock_hvac_client
    ):
        client = VaultClient(
            url="http://localhost:8200",
            role_id="123",
            secret_id="xyz",
            secrets_base_path="prefix",
            client=mock_hvac_client,
        )
        ensure_auth = mocker.patch.object(client, "_ensure_auth")
        ensure_auth.side_effect = [VaultError()]
        with pytest.raises(VaultError):
            client.check_authentication()
        ensure_auth.assert_called_once()


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


class TestGetRegionVaultClientIfEnabled:
    def test_cached(self, mocker):
        mock_get_client = mocker.patch.object(
            vault, "_get_region_vault_client"
        )
        mock_get_config = mocker.patch.object(Config.objects, "get_config")
        mock_get_config.return_value = True

        get_region_vault_client_if_enabled()
        get_region_vault_client_if_enabled()
        mock_get_client.assert_called_once()
        mock_get_config.assert_called_once()

    def test_no_client_if_not_enabled(self, factory, mocker):
        mock_get_client = mocker.patch.object(vault, "get_region_vault_client")
        mocker.patch.object(Config.objects, "get_config").return_value = False
        assert get_region_vault_client_if_enabled() is None
        mock_get_client.assert_not_called()

    def test_returns_client_if_enabled(self, factory, mocker):
        mock_get_client = mocker.patch.object(vault, "get_region_vault_client")
        mock_get_client.return_value = {}
        mocker.patch.object(Config.objects, "get_config").return_value = True
        assert get_region_vault_client_if_enabled() is not None
        mock_get_client.assert_called_once()


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


class TestConfigureRegionWithVault:
    def test_configures_region(self, factory, mocker, vault_regionconfig):
        url = "http://vault:8200"
        role_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        wrapped_token = factory.make_name("uuid")
        secrets_path = factory.make_name("uuid")
        secrets_mount = factory.make_name("uuid")

        mocker.patch.object(vault, "unwrap_secret").return_value = secret_id
        check_mock = mocker.patch.object(vault, "check_approle_permissions")

        vault.configure_region_with_vault(
            url=url,
            role_id=role_id,
            wrapped_token=wrapped_token,
            secrets_path=secrets_path,
            secrets_mount=secrets_mount,
        )

        assert vault_regionconfig["vault_url"] == url
        assert vault_regionconfig["vault_approle_id"] == role_id
        assert vault_regionconfig["vault_secret_id"] == secret_id
        assert vault_regionconfig["vault_secrets_path"] == secrets_path
        assert vault_regionconfig["vault_secrets_mount"] == secrets_mount
        check_mock.assert_called_once_with(
            url=url,
            role_id=role_id,
            secret_id=secret_id,
            secrets_path=secrets_path,
            secrets_mount=secrets_mount,
        )


class TestCheckApprolePermissions:
    def test_performs_expected_actions(self, mocker, factory):
        client = mocker.patch.object(vault, "VaultClient").return_value

        url = "http://vault:8200"
        role_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        secrets_path = factory.make_name("uuid")
        secrets_mount = factory.make_name("uuid")
        expected_path = f"test-{role_id}"

        vault.check_approle_permissions(
            url=url,
            role_id=role_id,
            secret_id=secret_id,
            secrets_path=secrets_path,
            secrets_mount=secrets_mount,
        )

        client.set.assert_called_once_with(expected_path, ANY)
        client.get.assert_called_once_with(expected_path)
        client.delete.assert_called_once_with(expected_path)
