#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests that _configure forwards binding/hardening vars to the template."""

from contextlib import contextmanager
import os
from unittest.mock import MagicMock

import maascommon.hardening as hardening_module
from maastesting.testcase import MAASTestCase
from provisioningserver.config import ClusterConfiguration
import provisioningserver.rackdservices.http as http_module
from provisioningserver.rackdservices.http import RackHTTPService


def _make_service():
    svc = RackHTTPService.__new__(RackHTTPService)
    svc._resource_root = "/tmp"
    return svc


class TestNginxHardeningVarsPassthrough(MAASTestCase):
    """Verify _configure forwards binding/hardening context to the template."""

    def _run_configure(self, hardening_active, api_bind="", **extra):
        """Run _configure and return the dict passed to template.substitute."""
        captured = {}

        def fake_substitute(ctx):
            captured.update(ctx)
            return "server {}"

        mock_template = MagicMock()
        mock_template.substitute.side_effect = fake_substitute

        @contextmanager
        def fake_cluster_open():
            m = MagicMock(spec=ClusterConfiguration)
            m.hardening_enabled = "on" if hardening_active else "auto"
            m.api_bind = api_bind
            m.api_bind6 = extra.get("api_bind6", "")
            m.api_upstream_port = extra.get("api_upstream_port", 5240)
            m.api_rate_limit_rate = extra.get("api_rate_limit_rate", "10r/s")
            m.api_rate_limit_burst = extra.get("api_rate_limit_burst", 20)
            m.api_conn_limit = extra.get("api_conn_limit", 100)
            yield m

        self.patch(http_module, "load_template", lambda *_: mock_template)
        self.patch(http_module, "get_root_path", MagicMock)
        self.patch(http_module, "get_maas_run_path", MagicMock)
        self.patch(
            http_module,
            "get_maas_data_path",
            lambda *_: "/var/lib/maas/image-storage",
        )
        self.patch(
            http_module,
            "compose_http_config_path",
            lambda *_: "/tmp/rackd.nginx.conf",
        )
        self.patch(http_module, "atomic_write")
        self.patch(os, "makedirs")
        self.patch(ClusterConfiguration, "open", fake_cluster_open)
        self.patch(
            hardening_module, "is_hardening_enabled", lambda: hardening_active
        )

        _make_service()._configure([])
        return captured

    def test_non_hardening_passes_hardening_false(self):
        captured = self._run_configure(hardening_active=False)
        assert captured.get("hardening") is False

    def test_hardening_on_passes_hardening_true_and_binds(self):
        captured = self._run_configure(
            hardening_active=True,
            api_bind="127.0.0.1",
            api_bind6="fd00::5",
        )
        assert captured.get("hardening") is True
        assert "127.0.0.1:5248" in captured.get("api_listen")
        assert "[fd00::5]:5248" in captured.get("api_listen")

    def test_upstream_port_forwarded(self):
        captured = self._run_configure(
            hardening_active=False, api_upstream_port=6240
        )
        assert captured.get("api_upstream_port") == 6240

    def test_rate_limit_and_conn_vars_forwarded(self):
        captured = self._run_configure(
            hardening_active=True,
            api_rate_limit_rate="5r/s",
            api_rate_limit_burst=10,
            api_conn_limit=50,
        )
        assert captured.get("api_rate_limit_rate") == "5r/s"
        assert captured.get("api_rate_limit_burst") == 10
        assert captured.get("api_conn_limit") == 50
