#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioningserver.server."""

from pathlib import Path
from unittest.mock import patch

from fixtures import EnvironmentVariable
from maastesting.testcase import MAASTestCase


class TestRunSocketCleanup(MAASTestCase):
    """Tests for stale dhcpd.sock cleanup in run()."""

    def test_run_removes_stale_socket(self):
        from provisioningserver import server

        tmpdir = self.make_dir()
        sock_path = Path(tmpdir) / "dhcpd.sock"
        sock_path.touch()
        self.assertTrue(sock_path.exists())
        self.useFixture(EnvironmentVariable("MAAS_DATA", tmpdir))
        with patch.object(server, "runService") as mock_run:
            server.run()
            mock_run.assert_called_once_with("maas-rackd")
        self.assertFalse(sock_path.exists())

    def test_run_handles_missing_socket(self):
        from provisioningserver import server

        tmpdir = self.make_dir()
        self.useFixture(EnvironmentVariable("MAAS_DATA", tmpdir))
        with patch.object(server, "runService") as mock_run:
            server.run()
            mock_run.assert_called_once_with("maas-rackd")

    def test_run_handles_unwritable_socket_path(self):
        from provisioningserver import server

        self.useFixture(
            EnvironmentVariable("MAAS_DATA", "/nonexistent/path")
        )
        with patch.object(server, "runService") as mock_run:
            server.run()
            mock_run.assert_called_once_with("maas-rackd")
