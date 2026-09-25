# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for FIPS power validation helpers."""

from unittest.mock import patch

from django.core.exceptions import ValidationError

from maasserver.forms.fips_power import (
    validate_power_params_fips,
    validate_power_pass_complexity,
)
from maastesting.testcase import MAASTestCase


class TestValidatePowerParamsFips(MAASTestCase):
    def test_noop_when_fips_disabled(self):
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=False
        ):
            # apc is FIPS-unsupported, but FIPS is off so no exception
            validate_power_params_fips("apc", {})

    def test_rejects_unsupported_driver_in_fips(self):
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            exc = self.assertRaises(
                ValidationError, validate_power_params_fips, "apc", {}
            )
            self.assertEqual("fips_violation", exc.code)

    def test_rejected_driver_emits_audit_event(self):
        with (
            patch(
                "maasserver.forms.fips_power.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "maasserver.forms.fips_power.log_fips_driver_rejected"
            ) as mock_log,
        ):
            self.assertRaises(
                ValidationError, validate_power_params_fips, "apc", {}
            )
            mock_log.assert_called_once()
            self.assertEqual("apc", mock_log.call_args.kwargs["driver"])
            self.assertIn("SNMPv1", mock_log.call_args.kwargs["reason"])

    def test_accepts_compliant_driver_in_fips(self):
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            # Should not raise
            validate_power_params_fips("ipmi", {"cipher_suite_id": "17"})

    def test_rejects_ipmi_non_fips_cipher(self):
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            exc = self.assertRaises(
                ValidationError,
                validate_power_params_fips,
                "ipmi",
                {"cipher_suite_id": "3"},
            )
            self.assertEqual("fips_violation", exc.code)

    def test_rejects_webhook_ssl_disabled(self):
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            exc = self.assertRaises(
                ValidationError,
                validate_power_params_fips,
                "webhook",
                {"power_verify_ssl": "n"},
            )
            self.assertEqual("fips_violation", exc.code)

    def test_accepts_lxd_driver_in_fips(self):
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            # Should not raise
            validate_power_params_fips("lxd", {})


class TestValidatePowerPassComplexity(MAASTestCase):
    def _patch(self, active):
        return patch(
            "maasserver.forms.fips_power.is_hardening_enabled",
            return_value=active,
        )

    def test_noop_when_hardening_inactive(self):
        with self._patch(False):
            validate_power_pass_complexity({"power_pass": "weak"})

    def test_rejects_weak_password_when_hardening(self):
        with self._patch(True):
            exc = self.assertRaises(
                ValidationError,
                validate_power_pass_complexity,
                {"power_pass": "weak"},
            )
        self.assertEqual("password_complexity", exc.code)

    def test_accepts_strong_password(self):
        with self._patch(True):
            validate_power_pass_complexity({"power_pass": "Str0ng!Pass#2026"})

    def test_skips_empty_password(self):
        with self._patch(True):
            validate_power_pass_complexity({"power_pass": ""})
