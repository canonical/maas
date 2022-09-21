from datetime import datetime, timedelta, timezone

import pytest

from maasserver import vault
from maasserver.vault import (
    _get_region_vault_client,
    AppRole,
    get_region_vault_client,
    hvac,
    VaultClient,
    VaultConfigurator,
)
from provisioningserver.utils.env import MAAS_UUID


@pytest.mark.usefixtures("mock_hvac_client")
class TestVaultClient:
    def test_set(self, mock_vault_kv):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_vault_kv.store == {"prefix/mysecret": value}

    def test_set_custom_mount(self, mock_vault_kv):
        mock_vault_kv.expected_mount_point = "other/secret/mount"
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
            secrets_mount="other/secret/mount",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_vault_kv.store == {"prefix/mysecret": value}

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

    def test_delete(self, mock_vault_kv):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        client.delete("mysecret")
        assert mock_vault_kv.store == {}

    def test_auth_on_request(self, mock_hvac_client):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
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
            secrets_base_path="prefix",
            role_id="123",
            secret_id="xyz",
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
@pytest.mark.usefixtures("vault_regionconfig")
class TestGetRegionVaultClient:
    def test_cached(self, mocker):
        get_region_vault_client.cache_clear()
        mock_get_client = mocker.patch.object(
            vault, "_get_region_vault_client"
        )
        get_region_vault_client()
        get_region_vault_client()
        mock_get_client.assert_called_once()

    def test_no_client_if_no_maas_uuid(self):
        MAAS_UUID.set(None)
        assert _get_region_vault_client() is None

    def test_no_client_if_not_all_configs(self, factory, vault_regionconfig):
        MAAS_UUID.set(factory.make_name("uuid"))
        # the secret is not set
        vault_regionconfig["vault_url"] = "http://vault:8200"
        vault_regionconfig["vault_approle_id"] = "x-y-z"
        assert _get_region_vault_client() is None

    def test_get_client(self, factory, vault_regionconfig):
        MAAS_UUID.set(factory.make_name("uuid"))
        approle_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        vault_regionconfig["vault_url"] = "http://vault:8200"
        vault_regionconfig["vault_approle_id"] = approle_id
        vault_regionconfig["vault_secret_id"] = secret_id
        client = _get_region_vault_client()
        assert isinstance(client, VaultClient)
        assert client._role_id == approle_id
        assert client._secret_id == secret_id

    def test_get_client_with_custom_secrets_mount(
        self, factory, vault_regionconfig
    ):
        MAAS_UUID.set(factory.make_name("uuid"))
        approle_id = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        vault_regionconfig["vault_url"] = "http://vault:8200"
        vault_regionconfig["vault_approle_id"] = approle_id
        vault_regionconfig["vault_secret_id"] = secret_id
        vault_regionconfig["vault_secrets_mount"] = "other/secrets"
        client = _get_region_vault_client()
        assert client._secrets_mount == "other/secrets"


class TestVaultConfigurator:
    def test_configure_policies(self, factory, mock_hvac_client):
        maas_uuid = factory.make_name("uuid")
        secrets_mount = factory.make_name("secret")
        configurator = VaultConfigurator(
            "http://vault:8200",
            "sekret",
            maas_uuid,
            secrets_mount=secrets_mount,
        )
        configurator.configure_policies()
        (
            rolemanager_call,
            region_call,
        ) = mock_hvac_client.sys.create_or_update_policy.mock_calls
        assert (
            rolemanager_call.kwargs["name"] == f"maas-{maas_uuid}-rolemanager"
        )
        rolemanager_policy = rolemanager_call.kwargs["policy"]
        assert (
            f'"auth/approle/role/maas-{maas_uuid}-*" {{' in rolemanager_policy
        )
        assert region_call.kwargs["name"] == f"maas-{maas_uuid}-region"
        region_policy = region_call.kwargs["policy"]
        assert (
            f'path "{secrets_mount}/metadata/maas-{maas_uuid}/" {{'
            in region_policy
        )
        assert (
            f'path "{secrets_mount}/data/maas-{maas_uuid}/*" {{'
            in region_policy
        )

    def test_get_approle_with_secret(self, factory, mock_hvac_client):
        configurator = VaultConfigurator("http://vault:8200", "sekret", "uuid")
        policy = factory.make_name("policy")
        role_id = factory.make_name("role-id")
        secret_id = factory.make_name("secret-id")
        mock_hvac_client.auth.approle.read_role_id.return_value = {
            "data": {"role_id": role_id}
        }
        mock_hvac_client.auth.approle.generate_secret_id.return_value = {
            "data": {"secret_id": secret_id}
        }

        approle = configurator.get_approle_with_secret(policy)
        assert approle == AppRole(
            name=policy, role_id=role_id, secret_id=secret_id
        )
        mock_hvac_client.auth.approle.create_or_update_approle.assert_called_once_with(
            role_name=policy,
            token_policies=[policy],
            token_ttl="5m",
            token_max_ttl="5m",
        )
        mock_hvac_client.auth.approle.read_role_id.assert_called_once_with(
            role_name=policy
        )
        mock_hvac_client.auth.approle.generate_secret_id.assert_called_once_with(
            role_name=policy
        )

    def test_get_approle_with_secret_with_suffix(
        self, factory, mock_hvac_client
    ):
        configurator = VaultConfigurator("http://vault:8200", "sekret", "uuid")
        policy = factory.make_name("policy")
        suffix = factory.make_name("suffix")
        configurator.get_approle_with_secret(policy, name_suffix=suffix)
        mock_hvac_client.auth.approle.create_or_update_approle.assert_called_once_with(
            role_name=f"{policy}-{suffix}",
            token_policies=[policy],
            token_ttl="5m",
            token_max_ttl="5m",
        )
