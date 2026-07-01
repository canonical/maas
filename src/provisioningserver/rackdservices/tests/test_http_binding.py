#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests that _configure forwards hardening vars to the NGINX template."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from maastesting.testcase import MAASTestCase
from provisioningserver.rackdservices.http import RackHTTPService


def _make_service():
    svc = RackHTTPService.__new__(RackHTTPService)
    svc._resource_root = "/tmp"
    return svc


class TestNginxHardeningVarsPassthrough(MAASTestCase):
    """Verify _configure forwards hardening context to the NGINX template."""

    def _run_configure(self, hardening_active, api_bind="0.0.0.0", **extra):
        """Run _configure and return the dict passed to template.substitute."""
        captured = {}

        def fake_substitute(ctx):
            captured.update(ctx)
            return "server {}"

        mock_template = MagicMock()
        mock_template.substitute.side_effect = fake_substitute

        @contextmanager
        def fake_cluster_open():
            m = MagicMock()
            m.hardening_enabled = "on" if hardening_active else "auto"
            m.api_bind = api_bind
            m.api_tls_cert = extra.get("api_tls_cert", "")
            m.api_tls_key = extra.get("api_tls_key", "")
            m.api_tls_dhparam = extra.get("api_tls_dhparam", "")
            m.api_rate_limit_rate = extra.get("api_rate_limit_rate", "10r/s")
            m.api_rate_limit_burst = extra.get("api_rate_limit_burst", 20)
            m.api_conn_limit = extra.get("api_conn_limit", 100)
            yield m

        patches = [
            patch(
                "provisioningserver.rackdservices.http.load_template",
                return_value=mock_template,
            ),
            patch(
                "provisioningserver.rackdservices.http.get_root_path",
                return_value=MagicMock(
                    __truediv__=lambda s, o: MagicMock(
                        __str__=lambda x: "/snap"
                    )
                ),
            ),
            patch(
                "provisioningserver.rackdservices.http.get_maas_run_path",
                return_value=MagicMock(
                    __truediv__=lambda s, o: MagicMock(
                        __str__=lambda x: "/run/maas/tmp.sock"
                    )
                ),
            ),
            patch(
                "provisioningserver.rackdservices.http.get_maas_data_path",
                return_value="/var/lib/maas/image-storage",
            ),
            patch(
                "provisioningserver.rackdservices.http.compose_http_config_path",
                return_value="/tmp/rackd.nginx.conf",
            ),
            patch("provisioningserver.rackdservices.http.atomic_write"),
            patch("os.makedirs"),
            patch(
                "provisioningserver.config.ClusterConfiguration.open",
                side_effect=fake_cluster_open,
            ),
            patch(
                "maascommon.hardening.is_hardening_enabled",
                return_value=hardening_active,
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        _make_service()._configure([])
        return captured

    def test_non_hardening_passes_hardening_false(self):
        captured = self._run_configure(hardening_active=False)
        assert captured.get("hardening") is False

    def test_hardening_on_passes_hardening_true_and_api_bind(self):
        captured = self._run_configure(
            hardening_active=True,
            api_bind="127.0.0.1",
            api_tls_cert="/etc/maas/tls.crt",
            api_tls_key="/etc/maas/tls.key",
        )
        assert captured.get("hardening") is True
        assert captured.get("api_bind") == "127.0.0.1"
        assert captured.get("api_tls_cert") == "/etc/maas/tls.crt"
        assert captured.get("api_tls_key") == "/etc/maas/tls.key"

    def test_rate_limit_and_conn_vars_forwarded(self):
        captured = self._run_configure(
            hardening_active=True,
            api_tls_dhparam="/etc/maas/dhparam.pem",
            api_rate_limit_rate="5r/s",
            api_rate_limit_burst=10,
            api_conn_limit=50,
        )
        assert captured.get("api_rate_limit_rate") == "5r/s"
        assert captured.get("api_rate_limit_burst") == 10
        assert captured.get("api_conn_limit") == 50
        assert captured.get("api_tls_dhparam") == "/etc/maas/dhparam.pem"
