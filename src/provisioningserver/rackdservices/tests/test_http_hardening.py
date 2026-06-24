#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for NGINX template hardening conditionals (rack).

The rack HTTP server never requires TLS: rack clients (enlisting/commissioning
machines, bootloaders) cannot be assumed to support it. Hardening only adds
security response headers, rate limiting is applied regardless of hardening,
and binding is driven by api_bind/api_bind6.
"""

import tempita

from maastesting.testcase import MAASTestCase
from provisioningserver.rackdservices.http import compose_listen_addresses
from provisioningserver.utils import locate_template


def _render(extra: dict | None = None) -> str:
    """Render the rackd.nginx.conf template with base vars plus extras."""
    base = {
        "upstream_http": [],
        "machine_resources": "/usr/share/maas",
        "maas_agent_httpproxy_socket_path": "/run/maas/httpproxy.sock",
        "maas_agent_http_socket_path": "/run/maas/agent-http.sock",
        "boot_resources_dir": "/var/lib/maas/image-storage",
        "hardening": False,
        "api_upstream_port": 5240,
        "api_rate_limit_rate": "10r/s",
        "api_rate_limit_burst": 20,
        "api_conn_limit": 100,
    }
    if extra:
        base.update(extra)
    base["api_listen"] = compose_listen_addresses(
        5248, base.pop("api_bind", ""), base.pop("api_bind6", "")
    )
    tpl = tempita.Template.from_filename(
        locate_template("http", "rackd.nginx.conf.template"),
        encoding="UTF-8",
    )
    return tpl.substitute(base)


HARDENING_VARS = {
    "hardening": True,
    "api_bind": "10.0.0.5",
    "api_bind6": "",
    "api_rate_limit_rate": "10r/s",
    "api_rate_limit_burst": 20,
    "api_conn_limit": 100,
}

# Same as HARDENING_VARS but with wildcard binding (empty api_bind/api_bind6),
# producing listen [::]:5248 + listen 5248 instead of a specific address.
HARDENING_VARS_WILDCARD = {**HARDENING_VARS, "api_bind": "", "api_bind6": ""}


class TestNginxTemplateNeverTLS(MAASTestCase):
    """The rack server is plain HTTP on 5248 in every mode."""

    def test_listen_on_5248_without_hardening(self):
        rendered = _render()
        self.assertIn("listen [::]:5248;", rendered)
        self.assertIn("listen 5248;", rendered)

    def test_no_ssl_directives_without_hardening(self):
        rendered = _render()
        self.assertNotIn("ssl_protocols", rendered)
        self.assertNotIn("ssl_certificate", rendered)

    def test_no_ssl_directives_with_hardening(self):
        rendered = _render(HARDENING_VARS)
        self.assertNotIn("ssl_protocols", rendered)
        self.assertNotIn("ssl_certificate", rendered)
        self.assertNotIn(" ssl;", rendered)
        self.assertNotIn("Strict-Transport-Security", rendered)


class TestNginxTemplateBinding(MAASTestCase):
    """Binding is driven by api_bind / api_bind6."""

    def test_wildcard_when_no_bind(self):
        rendered = _render({"api_bind": "", "api_bind6": ""})
        self.assertIn("listen [::]:5248;", rendered)
        self.assertIn("listen 5248;", rendered)

    def test_ipv4_bind_only(self):
        rendered = _render({"api_bind": "10.0.0.5", "api_bind6": ""})
        self.assertIn("listen 10.0.0.5:5248;", rendered)
        self.assertNotIn("listen 5248;", rendered)
        self.assertNotIn("listen [::]:5248;", rendered)

    def test_ipv6_bind_only(self):
        rendered = _render({"api_bind": "", "api_bind6": "fd00::5"})
        self.assertIn("listen [fd00::5]:5248;", rendered)
        self.assertNotIn("listen 5248;", rendered)
        self.assertNotIn("listen [::]:5248;", rendered)

    def test_dual_stack_bind(self):
        rendered = _render({"api_bind": "10.0.0.5", "api_bind6": "fd00::5"})
        self.assertIn("listen 10.0.0.5:5248;", rendered)
        self.assertIn("listen [fd00::5]:5248;", rendered)


class TestNginxTemplateUpstreamPort(MAASTestCase):
    """The upstream region API port is configurable, default 5240."""

    def test_default_upstream_port(self):
        rendered = _render({"upstream_http": ["10.0.0.1"]})
        self.assertIn("server 10.0.0.1:5240;", rendered)

    def test_custom_upstream_port(self):
        rendered = _render(
            {"upstream_http": ["10.0.0.1"], "api_upstream_port": 6240}
        )
        self.assertIn("server 10.0.0.1:6240;", rendered)


class TestNginxTemplateRateLimiting(MAASTestCase):
    """Rate/burst/conn limits apply with defaults regardless of hardening."""

    def test_rate_limit_zone_present_without_hardening(self):
        rendered = _render(
            {
                "api_rate_limit_rate": "5r/s",
                "api_rate_limit_burst": 10,
                "api_conn_limit": 50,
            }
        )
        self.assertIn(
            "limit_req_zone $binary_remote_addr zone=api_rate:10m rate=5r/s;",
            rendered,
        )
        self.assertIn(
            "limit_conn_zone $binary_remote_addr zone=api_conn:10m;", rendered
        )

    def test_rate_limit_applied_with_and_without_hardening(self):
        for extra in (None, HARDENING_VARS):
            rendered = _render(extra)
            self.assertIn(
                "limit_req zone=api_rate burst=20 nodelay;", rendered
            )
            self.assertIn("limit_conn api_conn 100;", rendered)

    def test_no_rate_limit_zone_when_rate_empty(self):
        # api_rate_limit_burst and api_conn_limit are only interpolated inside
        # the {{if api_rate_limit_rate}} block, so they are not required here.
        rendered = _render({"api_rate_limit_rate": ""})
        self.assertNotIn("limit_req_zone", rendered)
        self.assertNotIn("limit_conn_zone", rendered)


class TestNginxTemplateSecurityHeaders(MAASTestCase):
    """Security headers are added only when hardening is active."""

    def test_no_security_headers_without_hardening(self):
        rendered = _render()
        self.assertNotIn("X-Frame-Options", rendered)
        self.assertNotIn("Content-Security-Policy", rendered)
        self.assertNotIn("server_tokens off;", rendered)

    def test_security_headers_with_hardening(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("server_tokens off;", rendered)
        self.assertIn('add_header X-Frame-Options "DENY" always;', rendered)
        self.assertIn(
            'add_header X-Content-Type-Options "nosniff" always;', rendered
        )
        self.assertIn(
            'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
            rendered,
        )
        self.assertIn(
            'add_header X-XSS-Protection "1; mode=block" always;', rendered
        )

    def test_content_security_policy_with_hardening(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn(
            "add_header Content-Security-Policy"
            " \"default-src 'none'; frame-ancestors 'none'\" always;",
            rendered,
        )

    def test_trace_and_options_blocked_with_444(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("return 444;", rendered)
        self.assertIn("TRACE", rendered)
        self.assertIn("OPTIONS", rendered)

    def test_no_trace_block_without_hardening(self):
        rendered = _render()
        self.assertNotIn("return 444;", rendered)


class TestNginxTemplateLocations(MAASTestCase):
    """Location blocks are unaffected by hardening."""

    def test_location_blocks_present_regardless_of_hardening(self):
        for extra in (None, HARDENING_VARS):
            rendered = _render(extra)
            self.assertIn("location /machine-resources/", rendered)
            self.assertIn("proxy_pass http://localhost:5249/boot/;", rendered)
