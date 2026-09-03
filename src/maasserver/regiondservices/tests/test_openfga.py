# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
import tempfile

from fixtures import EnvironmentVariableFixture
import yaml

from maasserver.regiondservices import openfga as openfga_module
from maasserver.testing.testcase import MAASTestCase


class TestRegionOpenFGAService(MAASTestCase):
    def _patch_database_config(self, host, port, user, password, name):
        settings = self.patch(openfga_module, "settings")
        settings.DATABASES = {
            "default": {
                "HOST": host,
                "PORT": str(port),
                "USER": user,
                "PASSWORD": password,
                "NAME": name,
            }
        }
        connection = self.patch(openfga_module, "django_connection")
        connection._alias = "default"

    def test_writes_unix_socket_config(self):
        self._patch_database_config(
            "/var/run/postgresql", 5432, "maas", "secret", "maasdb"
        )

        with tempfile.TemporaryDirectory() as tmp:
            self.patch(
                openfga_module, "get_maas_data_path"
            ).return_value = Path(tmp)
            openfga_module.RegionOpenFGAService()._configure()
            path = Path(tmp) / "openfga.yaml"

            config = yaml.safe_load(path.read_text())
            self.assertEqual(
                config["database_uri"],
                "postgres://maas:secret@/maasdb?host="
                "%2Fvar%2Frun%2Fpostgresql&search_path=openfga",
            )
            self.assertEqual(config["openfga_max_open_conns"], 3)
            self.assertEqual(config["openfga_max_idle_conns"], 1)
            self.assertEqual(oct(path.stat().st_mode)[-3:], "600")

    def test_writes_tcp_config(self):
        self._patch_database_config(
            "db.example.com", 5433, "maas", "secret", "maasdb"
        )

        with tempfile.TemporaryDirectory() as tmp:
            self.patch(
                openfga_module, "get_maas_data_path"
            ).return_value = Path(tmp)
            openfga_module.RegionOpenFGAService()._configure()
            path = Path(tmp) / "openfga.yaml"

            config = yaml.safe_load(path.read_text())
            self.assertEqual(
                config["database_uri"],
                "postgres://maas:secret@db.example.com:5433/maasdb"
                "?search_path=openfga",
            )

    def test_no_password_omits_auth_prefix(self):
        self._patch_database_config(
            "/var/run/postgresql", 5432, "maas", "", "maasdb"
        )

        with tempfile.TemporaryDirectory() as tmp:
            self.patch(
                openfga_module, "get_maas_data_path"
            ).return_value = Path(tmp)
            openfga_module.RegionOpenFGAService()._configure()
            path = Path(tmp) / "openfga.yaml"

            config = yaml.safe_load(path.read_text())
            self.assertTrue(
                config["database_uri"].startswith("postgres://maas@/maasdb?")
            )

    def test_writes_config_to_maas_data_path(self):
        self._patch_database_config(
            "localhost", 5432, "maas", "secret", "maasdb"
        )

        data_dir = Path(self.make_dir())
        self.useFixture(EnvironmentVariableFixture("MAAS_DATA", str(data_dir)))
        self.useFixture(
            EnvironmentVariableFixture("MAAS_OPENFGA_CONFIG_DIR", None)
        )

        openfga_module.RegionOpenFGAService()._configure()

        config_path = data_dir / "openfga.yaml"
        self.assertTrue(config_path.exists())
        config = yaml.safe_load(config_path.read_text())
        self.assertTrue(
            config["database_uri"].startswith("postgres://maas:secret@")
        )
