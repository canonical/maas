# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import os
import subprocess
import time

import pytest
import yaml

from maasserver.regiondservices.openfga import build_openfga_dsn
from tests.maasapiserver.fixtures.db import db, db_connection, test_config

__all__ = [
    "db_connection",
    "db",
    "test_config",
    "openfga_socket_path",
    "openfga_server",
    "mock_maas_env",
    "project_root_path",
]


@pytest.fixture
def project_root_path(request):
    return request.config.rootpath


@pytest.fixture
def openfga_socket_path(tmpdir):
    return tmpdir / "openfga-http.sock"


@pytest.fixture
def mock_maas_env(monkeypatch, openfga_socket_path):
    """Mocks the MAAS_OPENFGA_HTTP_SOCKET_PATH environment variable."""
    monkeypatch.setenv(
        "MAAS_OPENFGA_HTTP_SOCKET_PATH", str(openfga_socket_path)
    )


@pytest.fixture
def openfga_server(tmpdir, project_root_path, openfga_socket_path, db):
    """Fixture to start the OpenFGA server as a subprocess for testing.

    The fixture writes an OpenFGA configuration file with a database URI built
    from the test database settings, matching what ``RegionOpenFGAService``
    generates at runtime.
    """
    binary_path = project_root_path / "src/maasopenfga/build/maas-openfga"

    env = os.environ.copy()
    env["MAAS_OPENFGA_HTTP_SOCKET_PATH"] = str(openfga_socket_path)
    env.pop("MAAS_OPENFGA_CONFIG", None)

    host = db.config.host
    port = db.config.port or 5432
    user = env["USER"]
    password = db.config.password or ""
    name = db.config.name

    dsn = build_openfga_dsn(host, port, user, password, name)

    config_path = tmpdir / "openfga.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(
            {
                "database_uri": dsn,
                "openfga_max_open_conns": 3,
                "openfga_max_idle_conns": 1,
            },
            f,
        )

    env["MAAS_OPENFGA_CONFIG"] = str(config_path)

    pid = subprocess.Popen(binary_path, env=env)

    timeout = timedelta(seconds=30)
    start_time = time.monotonic()
    while True:
        if time.monotonic() - start_time > timeout.total_seconds():
            pid.terminate()
            raise TimeoutError(
                "OpenFGA server did not start within the expected time."
            )
        if not openfga_socket_path.exists():
            time.sleep(0.5)
        else:
            break
    yield pid
    pid.terminate()
