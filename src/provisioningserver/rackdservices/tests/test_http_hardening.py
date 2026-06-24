#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for NGINX template hardening conditionals."""

import tempita

from maastesting.testcase import MAASTestCase
from provisioningserver.utils import locate_template


def _render(extra: dict | None = None) -> str:
    """Render the rackd.nginx.conf template with base vars plus extras."""
    base = {
        "upstream_http": [],
        "machine_resources": "/usr/share/maas",
        "maas_agent_httpproxy_socket_path": "/run/maas/httpproxy.sock",
        "maas_agent_http_socket_path": "/run/maas/agent-http.sock",
        "boot_resources_dir": "/var/lib/maas/image-storage",
    }
    if extra:
        base.update(extra)
    tpl = tempita.Template.from_filename(
        locate_template("http", "rackd.nginx.conf.template"),
        encoding="UTF-8",
    )
    return tpl.substitute(base)


HARDENING_VARS = {
    "hardening": True,
    "api_bind": "0.0.0.0",
    "api_tls_cert": "/etc/maas/tls/cert.pem",
    "api_tls_key": "/etc/maas/tls/key.pem",
    "api_tls_dhparam": "",
    "api_rate_limit_rate": "10r/s",
    "api_rate_limit_burst": 20,
    "api_conn_limit": 100,
}


class TestNginxTemplateNoHardening(MAASTestCase):
    """The template without hardening is identical to existing behaviour."""

    def test_listen_on_5248_without_hardening(self):
        rendered = _render()
        self.assertIn("listen [::]:5248;", rendered)
        self.assertIn("listen 5248;", rendered)

    def test_no_ssl_directives_without_hardening(self):
        rendered = _render()
        self.assertNotIn("ssl_protocols", rendered)
        self.assertNotIn("ssl_certificate", rendered)

    def test_no_security_headers_without_hardening(self):
        rendered = _render()
        self.assertNotIn("Strict-Transport-Security", rendered)
        self.assertNotIn("X-Frame-Options", rendered)

    def test_no_rate_limit_zone_without_hardening(self):
        rendered = _render()
        self.assertNotIn("limit_req_zone", rendered)
        self.assertNotIn("limit_conn_zone", rendered)

    def test_no_siem_log_format_without_hardening(self):
        rendered = _render()
        self.assertNotIn("log_format siem", rendered)

    def test_no_trace_block_without_hardening(self):
        rendered = _render()
        self.assertNotIn("return 405", rendered)

    def test_explicit_hardening_false_same_as_omitted(self):
        omitted = _render()
        explicit_false = _render({"hardening": False})
        self.assertEqual(omitted, explicit_false)

    def test_upstream_http_block_rendered(self):
        rendered = _render({"upstream_http": ["10.0.0.1"]})
        self.assertIn("server 10.0.0.1:5240;", rendered)

    def test_location_blocks_present(self):
        rendered = _render()
        self.assertIn("location /machine-resources/", rendered)
        self.assertIn("location / {", rendered)
        self.assertIn("proxy_pass http://localhost:5249/boot/;", rendered)


class TestNginxTemplateHardeningEnabled(MAASTestCase):
    """The template with hardening=True emits FIPS/STIG/CIS directives."""

    def test_ssl_protocols_tls12_tls13(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", rendered)

    def test_strict_transport_security_header(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn(
            "add_header Strict-Transport-Security "
            '"max-age=31536000; includeSubDomains" always;',
            rendered,
        )

    def test_rate_limit_zone_directive(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn(
            "limit_req_zone $binary_remote_addr zone=api_rate:10m rate=10r/s;",
            rendered,
        )

    def test_conn_limit_zone_directive(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn(
            "limit_conn_zone $binary_remote_addr zone=api_conn:10m;",
            rendered,
        )

    def test_siem_log_format(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("log_format siem", rendered)
        self.assertIn(
            "access_log /var/log/maas/http/access.log siem;", rendered
        )

    def test_ssl_listen_on_5443(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("listen 0.0.0.0:5443 ssl;", rendered)

    def test_ssl_certificate_directives(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("ssl_certificate /etc/maas/tls/cert.pem;", rendered)
        self.assertIn("ssl_certificate_key /etc/maas/tls/key.pem;", rendered)

    def test_ssl_ciphers_present(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("ssl_ciphers", rendered)
        self.assertIn("ECDHE-ECDSA-AES128-GCM-SHA256", rendered)

    def test_ssl_session_tickets_off(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("ssl_session_tickets off;", rendered)

    def test_server_tokens_off(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("server_tokens off;", rendered)

    def test_security_headers(self):
        rendered = _render(HARDENING_VARS)
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

    def test_content_security_policy_header(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn(
            "add_header Content-Security-Policy"
            " \"default-src 'none'; frame-ancestors 'none'\" always;",
            rendered,
        )

    def test_no_csp_without_hardening(self):
        rendered = _render()
        self.assertNotIn("Content-Security-Policy", rendered)

    def test_rate_limit_applied_in_server_block(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("limit_req zone=api_rate burst=20 nodelay;", rendered)
        self.assertIn("limit_conn api_conn 100;", rendered)

    def test_trace_blocked_with_405(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("return 405;", rendered)
        self.assertIn("TRACE", rendered)
        self.assertNotIn("OPTIONS", rendered)

    def test_5248_not_in_hardened_output(self):
        rendered = _render(HARDENING_VARS)
        self.assertNotIn("listen 5248;", rendered)
        self.assertNotIn("listen [::]:5248;", rendered)

    def test_location_blocks_still_present_with_hardening(self):
        rendered = _render(HARDENING_VARS)
        self.assertIn("location /machine-resources/", rendered)
        self.assertIn("proxy_pass http://localhost:5249/boot/;", rendered)


class TestNginxTemplateDhparam(MAASTestCase):
    """Tests for ssl_dhparam and ssl_stapling directives.

    After the N2 fix: ssl_stapling is always emitted in hardening mode;
    ssl_dhparam is independently conditional on api_tls_dhparam being set.
    """

    def test_stapling_always_on_when_hardening(self):
        """ssl_stapling is emitted in hardening mode even without dhparam."""
        rendered = _render(HARDENING_VARS)
        self.assertIn("ssl_stapling on;", rendered)
        self.assertIn("ssl_stapling_verify on;", rendered)
        self.assertNotIn("ssl_dhparam", rendered)

    def test_dhparam_emitted_when_set(self):
        vars_with_dhparam = dict(HARDENING_VARS)
        vars_with_dhparam["api_tls_dhparam"] = "/etc/maas/tls/dhparam.pem"
        rendered = _render(vars_with_dhparam)
        self.assertIn("ssl_stapling on;", rendered)
        self.assertIn("ssl_stapling_verify on;", rendered)
        self.assertIn("ssl_dhparam /etc/maas/tls/dhparam.pem;", rendered)

    def test_dhparam_absent_when_empty_string(self):
        vars_no_dhparam = dict(HARDENING_VARS)
        vars_no_dhparam["api_tls_dhparam"] = ""
        rendered = _render(vars_no_dhparam)
        self.assertNotIn("ssl_dhparam", rendered)

    def test_dhparam_absent_when_not_provided(self):
        vars_no_dhparam = dict(HARDENING_VARS)
        vars_no_dhparam.pop("api_tls_dhparam", None)
        rendered = _render(vars_no_dhparam)
        self.assertNotIn("ssl_dhparam", rendered)
