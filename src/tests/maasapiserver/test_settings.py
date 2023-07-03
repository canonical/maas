from pathlib import Path

import maasapiserver.settings
from maasapiserver.settings import (
    _construct_dsn,
    _get_default_db_config,
    api_service_socket_path,
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


class TestConstructDSN:
    def test_unix(self):
        assert (
            _construct_dsn("maasdb", "user", "pass", "/unix.socket", 12345)
            == "postgresql+asyncpg://user:pass@localhost/maasdb?host=/unix.socket&port=12345"
        )

    def test_host(self):
        assert (
            _construct_dsn("maasdb", "user", "pass", "host", 12345)
            == "postgresql+asyncpg://user:pass@host:12345/maasdb"
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
        assert (
            _get_default_db_config(region_config)
            == "postgresql+asyncpg://user:pass@host:12345/maasdb"
        )

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

        assert (
            _get_default_db_config(region_config)
            == "postgresql+asyncpg://user:pass@host:12345/maasdb"
        )
