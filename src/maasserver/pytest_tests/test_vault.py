from datetime import datetime, timedelta, timezone

import pytest

from maasserver.vault import hvac, VaultClient


class MockKVStore:
    def __init__(self):
        self.store = {}

    def create_or_update_secret(self, path, value):
        self.store[path] = value

    def read_secret(self, path):
        try:
            # include only relevant fields in response
            return {"data": {"data": self.store[path]}}
        except KeyError:
            raise hvac.exceptions.InvalidPath(
                url=f"http://localhost:8200/v1/secret/data/{path}",
                method="get",
            )

    def delete_latest_version_of_secret(self, path):
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
            secrets_base_path="secret/prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert mock_kv.store == {"secret/prefix/mysecret": value}

    def test_get(self):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="secret/prefix",
            role_id="123",
            secret_id="xyz",
        )
        value = {"foo": "bar"}
        client.set("mysecret", value)
        assert client.get("mysecret") == value

    def test_get_not_found(self):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="secret/prefix",
            role_id="123",
            secret_id="xyz",
        )
        with pytest.raises(hvac.exceptions.InvalidPath):
            client.get("mysecret")

    def test_delete(self, mock_kv):
        client = VaultClient(
            url="http://localhost:8200",
            secrets_base_path="secret/prefix",
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
            secrets_base_path="secret/prefix",
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
            secrets_base_path="secret/prefix",
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
