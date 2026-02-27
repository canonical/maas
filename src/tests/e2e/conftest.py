# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import os
import subprocess
import time

import pytest
import yaml

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
    """Fixture to start the OpenFGA server as a subprocess for testing. After the test is done, it ensures that the server process is terminated."""
    binary_path = project_root_path / "src/maasopenfga/build/maas-openfga"

    # Set the environment variable for the OpenFGA server to use the socket path in the temporary directory
    env = os.environ.copy()
    env["MAAS_OPENFGA_HTTP_SOCKET_PATH"] = str(openfga_socket_path)

    regiond_conf = {
        "database_host": db.config.host,
        "database_name": db.config.name,
        "database_user": "ubuntu",
    }

    # Write the regiond configuration to a file in the temporary directory
    with open(tmpdir / "regiond.conf", "w") as f:
        f.write(yaml.dump(regiond_conf))

    env["SNAP_DATA"] = str(tmpdir)

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
