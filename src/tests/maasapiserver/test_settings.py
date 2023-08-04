from pathlib import Path

import maasapiserver.settings
from maasapiserver.settings import (
    _get_default_db_config,
    api_service_socket_path,
    DatabaseConfig,
)
from maasserver.config import RegionConfiguration
from provisioningserver.path import get_maas_data_path
from provisioningserver.utils.env import MAAS_ID


class TestAPIServiceSocketPath:
    def test_path_from_env(self, monkeypatch):
        monkeypatch.setenv(
            "MAAS_APISERVER_HTTP_SOCKET_PATH",
            "/var/snap/maas/common/apiserver-http.sock",
        )
        assert api_service_socket_path() == Path(
            "/var/snap/maas/common/apiserver-http.sock"
        )

    def test_path_from_data_dir(self, monkeypatch):
        monkeypatch.delenv("MAAS_APISERVER_HTTP_SOCKET_PATH", raising=False)
        assert api_service_socket_path() == Path(
            get_maas_data_path("apiserver-http.sock")
        )


class TestDatabaseConfig:
    def test_unix(self):
        config = DatabaseConfig(
            "maasdb",
            username="user",
            password="pass",
            host="/unix.socket",
            port=12345,
        )
        assert (
            str(config.dsn)
            == "postgresql+asyncpg://user:***@/unix.socket:12345/maasdb"
        )

    def test_host(self):
        config = DatabaseConfig(
            "maasdb", username="user", password="pass", host="host", port=12345
        )
        assert (
            str(config.dsn)
            == "postgresql+asyncpg://user:***@host:12345/maasdb"
        )


class TestGetDefaultDBConfig:
    def test_local(self):
        region_config = RegionConfiguration(
            {
                "database_name": "maasdb",
                "database_user": "user",
                "database_pass": "pass",
                "database_host": "host",
                "database_port": 12345,
            }
        )
        config = _get_default_db_config(region_config)
        assert config.name == "maasdb"
        assert config.host == "host"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.port == 12345

    def test_vault(self, mocker):
        MAAS_ID.set("asdf")
        region_config = RegionConfiguration(
            {
                "database_host": "host",
                "database_port": 12345,
            }
        )
        mock_client = mocker.patch.object(
            maasapiserver.settings, "get_region_vault_client"
        ).return_value
        mock_client.get.return_value = {
            "name": "maasdb",
            "user": "user",
            "pass": "pass",
        }

        config = _get_default_db_config(region_config)
        assert config.name == "maasdb"
        assert config.host == "host"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.port == 12345
