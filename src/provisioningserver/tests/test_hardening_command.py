# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the ``maas-rack config-hardening`` command."""

from contextlib import redirect_stdout
import io
from unittest.mock import patch

from maastesting.testcase import MAASTestCase
from provisioningserver import hardening_command
from provisioningserver.config import ClusterConfiguration
from provisioningserver.testing.config import ClusterConfigurationFixture

_PATCH_CONFIGURE = patch(
    "provisioningserver.hardening_command.configure_hardening"
)


class _Base(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(ClusterConfigurationFixture())
        # `configure_hardening()` is process-global and latches after the
        # first call; each test patches it out and drives
        # `is_hardening_enabled()` directly instead.
        _PATCH_CONFIGURE.start()
        self.addCleanup(_PATCH_CONFIGURE.stop)

    @staticmethod
    def _capture(fn, *args):
        out = io.StringIO()
        code = 0
        with redirect_stdout(out):
            try:
                fn(*args)
            except SystemExit as exc:
                code = exc.code if exc.code is not None else 0
        return out.getvalue(), code


class TestCmdSetGetList(_Base):
    def test_set_and_get_scalar_key(self):
        hardening_command._cmd_set("rpc_bind", "10.0.0.5")
        with ClusterConfiguration.open() as config:
            self.assertEqual("10.0.0.5", config.rpc_bind)

    def test_set_and_get_list_key(self):
        hardening_command._cmd_set("api_bind", "10.0.0.5,10.0.0.6")
        with ClusterConfiguration.open() as config:
            self.assertEqual(["10.0.0.5", "10.0.0.6"], config.api_bind)

    def test_set_hardening_enabled_rejects_invalid_value(self):
        exc = self.assertRaises(
            SystemExit,
            hardening_command._cmd_set,
            "hardening_enabled",
            "bogus",
        )
        self.assertIn("hardening_enabled must be one of", str(exc))

    def test_set_hardening_enabled_accepts_known_values(self):
        hardening_command._cmd_set("hardening_enabled", "ON")
        with ClusterConfiguration.open() as config:
            self.assertEqual("on", config.hardening_enabled)

    def test_set_dns_bind_refused_outside_snap(self):
        with patch.object(
            hardening_command, "running_in_snap", return_value=False
        ):
            self.assertRaises(
                SystemExit,
                hardening_command._cmd_set,
                "dns_bind",
                "10.0.0.5",
            )

    def test_set_dns_bind_allowed_in_snap(self):
        with patch.object(
            hardening_command, "running_in_snap", return_value=True
        ):
            hardening_command._cmd_set("dns_bind", "10.0.0.5")
        with ClusterConfiguration.open() as config:
            self.assertEqual(["10.0.0.5"], config.dns_bind)

    def test_list_excludes_dns_keys_outside_snap(self):
        with patch.object(
            hardening_command, "running_in_snap", return_value=False
        ):
            output, _ = self._capture(hardening_command._cmd_list)
        self.assertNotIn("dns_bind", output)

    def test_list_includes_dns_keys_in_snap(self):
        with patch.object(
            hardening_command, "running_in_snap", return_value=True
        ):
            output, _ = self._capture(hardening_command._cmd_list)
        self.assertIn("dns_bind", output)


class TestCmdValidate(_Base):
    def test_inactive_hardening_reports_and_exits_zero(self):
        hardening_command._cmd_set("hardening_enabled", "off")
        with patch.object(
            hardening_command, "is_hardening_enabled", return_value=False
        ):
            output, code = self._capture(hardening_command._cmd_validate)
        self.assertIn("not active", output)
        self.assertEqual(0, code)

    def test_active_hardening_with_unset_binds_reports_violations(self):
        hardening_command._cmd_set("hardening_enabled", "on")
        with (
            patch.object(
                hardening_command, "running_in_snap", return_value=False
            ),
            patch.object(
                hardening_command, "is_hardening_enabled", return_value=True
            ),
        ):
            output, code = self._capture(hardening_command._cmd_validate)
        self.assertIn("WILDCARD_BIND_NOT_ALLOWED", output)
        self.assertIn("rpc_bind", output)
        self.assertEqual(1, code)

    def test_active_hardening_with_invalid_address_reports_invalid_bind(self):
        hardening_command._cmd_set("hardening_enabled", "on")
        hardening_command._cmd_set("api_bind", "not-an-ip")
        hardening_command._cmd_set("rpc_bind", "10.0.0.5")
        hardening_command._cmd_set("syslog_bind", "10.0.0.5")
        hardening_command._cmd_set("http_proxy_bind", "10.0.0.5")
        hardening_command._cmd_set("http_proxy_bind6", "fd00::5")
        hardening_command._cmd_set("api_bind6", "fd00::5")
        with (
            patch.object(
                hardening_command, "running_in_snap", return_value=False
            ),
            patch.object(
                hardening_command, "is_hardening_enabled", return_value=True
            ),
        ):
            output, code = self._capture(hardening_command._cmd_validate)
        self.assertIn("INVALID_BIND_ADDRESS", output)
        self.assertIn("api_bind", output)
        self.assertEqual(1, code)

    def test_all_binds_set_reports_ok(self):
        hardening_command._cmd_set("hardening_enabled", "on")
        for key, value in (
            ("api_bind", "10.0.0.5"),
            ("api_bind6", "fd00::5"),
            ("rpc_bind", "10.0.0.5"),
            ("syslog_bind", "10.0.0.5"),
            ("http_proxy_bind", "10.0.0.5"),
            ("http_proxy_bind6", "fd00::5"),
        ):
            hardening_command._cmd_set(key, value)
        with (
            patch.object(
                hardening_command, "running_in_snap", return_value=False
            ),
            patch.object(
                hardening_command, "is_hardening_enabled", return_value=True
            ),
        ):
            output, code = self._capture(hardening_command._cmd_validate)
        self.assertIn("OK", output)
        self.assertEqual(0, code)
