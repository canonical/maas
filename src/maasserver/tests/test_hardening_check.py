# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for hardening_check.py (notification sync).

Uses Django ORM (maasserver test suite).  Run via:
    bin/test.region maasserver.tests.test_hardening_check
"""

from maasserver.models import Notification
from maasserver.regiondservices.hardening_check import (
    HARDENING_CTRL_IDENT_PREFIX,
    HARDENING_NOTIFICATION_IDENT_PREFIX,
    sync_hardening_notifications,
)
from maasserver.testing.testcase import MAASServerTestCase
from maasservicelayer.services.hardening import _ident, HardeningViolation


def _make_violation(
    code: str, config_key: str = "api_tls_cert"
) -> HardeningViolation:
    return HardeningViolation(
        ident=_ident(code),
        code=code,
        message=f"Test violation: {code}",
        resolution="Run: maas config-hardening set api_tls_cert <path>",
        config_key=config_key,
        file_path=None,
    )


def _make_bind_violation(config_key: str = "api_bind") -> HardeningViolation:
    return HardeningViolation(
        ident=f"hardening-wildcard-bind-{config_key.replace('_', '-')}",
        code="WILDCARD_BIND_NOT_ALLOWED",
        message=f"{config_key} is not configured; would bind to all interfaces",
        resolution=f"Run: maas config-hardening set {config_key} <ip>",
        config_key=config_key,
        file_path=None,
    )


class TestSyncHardeningNotifications(MAASServerTestCase):
    def test_empty_violations_no_notifications_created(self):
        sync_hardening_notifications([])
        count = Notification.objects.filter(
            ident__startswith=HARDENING_NOTIFICATION_IDENT_PREFIX
        ).count()
        self.assertEqual(0, count)

    def test_violation_creates_error_notification(self):
        v = _make_violation("MISSING_TLS_CERT")
        sync_hardening_notifications([v])

        n = Notification.objects.get(ident=v.ident)
        self.assertEqual("error", n.category)
        self.assertTrue(n.admins)
        self.assertFalse(n.users)
        self.assertFalse(n.dismissable)
        self.assertIn("MISSING_TLS_CERT", n.context["code"])

    def test_violation_message_contains_resolution(self):
        v = _make_violation("MISSING_TLS_CERT")
        sync_hardening_notifications([v])
        n = Notification.objects.get(ident=v.ident)
        self.assertIn("config-hardening", n.message)

    def test_resolved_violation_cleared_on_next_sync(self):
        v = _make_violation("MISSING_TLS_CERT")
        sync_hardening_notifications([v])
        self.assertTrue(Notification.objects.filter(ident=v.ident).exists())
        sync_hardening_notifications([])
        self.assertFalse(Notification.objects.filter(ident=v.ident).exists())

    def test_unrelated_notifications_not_touched(self):
        Notification.objects.create_info_for_admins(
            "Unrelated", ident="some-other-ident"
        )
        sync_hardening_notifications([])
        self.assertTrue(
            Notification.objects.filter(ident="some-other-ident").exists()
        )

    def test_second_violation_replaces_first(self):
        v1 = _make_violation("MISSING_TLS_CERT")
        v2 = _make_violation("WEAK_DH_PARAMS")
        sync_hardening_notifications([v1])
        sync_hardening_notifications([v2])
        self.assertFalse(Notification.objects.filter(ident=v1.ident).exists())
        self.assertTrue(Notification.objects.filter(ident=v2.ident).exists())

    def test_multiple_violations_all_posted(self):
        violations = [
            _make_violation("MISSING_TLS_CERT"),
            _make_violation("WEAK_DH_PARAMS"),
            _make_violation("INSECURE_DB_SSLMODE", "database_sslmode"),
        ]
        sync_hardening_notifications(violations)
        for v in violations:
            self.assertTrue(
                Notification.objects.filter(ident=v.ident).exists(),
                f"Missing notification for {v.ident}",
            )

    def test_dismissable_is_false(self):
        v = _make_violation("MISSING_TLS_CERT")
        sync_hardening_notifications([v])
        n = Notification.objects.get(ident=v.ident)
        self.assertFalse(n.dismissable)

    def test_context_has_code_config_key_file_path(self):
        v = HardeningViolation(
            ident=_ident("MISSING_TLS_CERT"),
            code="MISSING_TLS_CERT",
            message="cert missing",
            resolution="fix it",
            config_key="api_tls_cert",
            file_path="/etc/maas/certs/tls.pem",
        )
        sync_hardening_notifications([v])
        n = Notification.objects.get(ident=v.ident)
        self.assertEqual("MISSING_TLS_CERT", n.context["code"])
        self.assertEqual("api_tls_cert", n.context["config_key"])
        self.assertEqual("/etc/maas/certs/tls.pem", n.context["file_path"])


class TestSyncHardeningNotificationsWithControllerId(MAASServerTestCase):
    """Bind violations are scoped per controller; non-bind ones are global."""

    CTRL_A = "abc123"
    CTRL_B = "def456"

    def _ctrl_ident(self, ctrl: str, config_key: str) -> str:
        return f"{HARDENING_CTRL_IDENT_PREFIX}{ctrl}-{config_key}"

    def test_bind_violation_uses_controller_scoped_ident(self):
        v = _make_bind_violation()
        sync_hardening_notifications([v], controller_id=self.CTRL_A)

        self.assertTrue(
            Notification.objects.filter(
                ident=self._ctrl_ident(self.CTRL_A, "api_bind")
            ).exists()
        )
        self.assertFalse(Notification.objects.filter(ident=v.ident).exists())

    def test_bind_violation_message_contains_controller_id(self):
        v = _make_bind_violation()
        sync_hardening_notifications([v], controller_id=self.CTRL_A)
        n = Notification.objects.get(
            ident=self._ctrl_ident(self.CTRL_A, "api_bind")
        )
        self.assertIn(self.CTRL_A, n.message)

    def test_bind_violation_context_contains_controller_id(self):
        v = _make_bind_violation()
        sync_hardening_notifications([v], controller_id=self.CTRL_A)
        n = Notification.objects.get(
            ident=self._ctrl_ident(self.CTRL_A, "api_bind")
        )
        self.assertEqual(self.CTRL_A, n.context["controller_id"])

    def test_non_bind_violation_keeps_global_ident_with_controller_id(self):
        v = _make_violation("MISSING_TLS_CERT")
        sync_hardening_notifications([v], controller_id=self.CTRL_A)

        self.assertTrue(Notification.objects.filter(ident=v.ident).exists())
        self.assertEqual(
            0,
            Notification.objects.filter(
                ident__startswith=f"{HARDENING_CTRL_IDENT_PREFIX}{self.CTRL_A}-"
            ).count(),
        )

    def test_stale_bind_notification_cleared_on_resolution(self):
        v = _make_bind_violation()
        sync_hardening_notifications([v], controller_id=self.CTRL_A)
        ctrl_ident = self._ctrl_ident(self.CTRL_A, "api_bind")
        self.assertTrue(Notification.objects.filter(ident=ctrl_ident).exists())
        sync_hardening_notifications([], controller_id=self.CTRL_A)
        self.assertFalse(
            Notification.objects.filter(ident=ctrl_ident).exists()
        )

    def test_other_controller_bind_notification_not_cleared(self):
        v = _make_bind_violation()
        sync_hardening_notifications([v], controller_id=self.CTRL_A)
        sync_hardening_notifications([v], controller_id=self.CTRL_B)

        ctrl_b_ident = self._ctrl_ident(self.CTRL_B, "api_bind")
        self.assertTrue(
            Notification.objects.filter(ident=ctrl_b_ident).exists()
        )
        sync_hardening_notifications([], controller_id=self.CTRL_A)
        self.assertTrue(
            Notification.objects.filter(ident=ctrl_b_ident).exists()
        )

    def test_multiple_bind_violations_all_scoped(self):
        violations = [
            _make_bind_violation(config_key="api_bind"),
            _make_bind_violation(config_key="api_bind6"),
        ]
        sync_hardening_notifications(violations, controller_id=self.CTRL_A)
        for config_key in ("api_bind", "api_bind6"):
            ident = self._ctrl_ident(self.CTRL_A, config_key)
            self.assertTrue(
                Notification.objects.filter(ident=ident).exists(),
                f"Missing scoped notification: {ident}",
            )


class TestHardeningIdentLength(MAASServerTestCase):
    """Controller-scoped idents must stay within Notification.ident max_length=40."""

    # All bind config_keys produced by HardeningValidator._validate_binds().
    BIND_CONFIG_KEYS = (
        "api_bind",
        "api_bind6",
        "prometheus_bind",
        "temporal_bind",
        "rpc_bind",
    )

    def _ctrl_ident(self, ctrl: str, config_key: str) -> str:
        return f"{HARDENING_CTRL_IDENT_PREFIX}{ctrl}-{config_key}"

    def test_all_bind_idents_within_40_chars(self):
        """Every (system_id, config_key) pair produces an ident <= 40 chars."""
        # system_id is a base-24 znums string; empirically 6 chars for the
        # full 24^6 space.  Use the 6-char maximum to confirm the invariant.
        system_id = "abc123"  # representative 6-char system_id
        for config_key in self.BIND_CONFIG_KEYS:
            ident = self._ctrl_ident(system_id, config_key)
            self.assertLessEqual(
                len(ident),
                40,
                f"ident {ident!r} is {len(ident)} chars — exceeds "
                f"Notification.ident max_length=40",
            )

    def test_scoped_ident_can_be_stored_and_retrieved(self):
        """An ident at the expected maximum length round-trips through the DB."""
        # prometheus_bind produces the longest ident; verify it persists.
        system_id = "abc123"
        config_key = "prometheus_bind"
        ident = self._ctrl_ident(system_id, config_key)
        v = _make_bind_violation(config_key=config_key)
        sync_hardening_notifications([v], controller_id=system_id)
        self.assertTrue(
            Notification.objects.filter(ident=ident).exists(),
            f"Notification with ident {ident!r} was not created",
        )
