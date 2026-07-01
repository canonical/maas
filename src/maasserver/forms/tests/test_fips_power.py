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


def _raises_validation_error(fn, *args, **kwargs):
    """Call fn and return the ValidationError raised, or None."""
    try:
        fn(*args, **kwargs)
        return None
    except ValidationError as exc:
        return exc


class TestValidatePowerParamsFips(MAASTestCase):
    def test_noop_when_fips_disabled(self):
        """When FIPS is disabled no exception is raised even for blocked drivers."""
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=False
        ):
            # apc is FIPS-unsupported, but FIPS is off so no exception
            validate_power_params_fips("apc", {})

    def test_rejects_unsupported_driver_in_fips(self):
        """An unsupported driver raises ValidationError with code fips_violation."""
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            exc = _raises_validation_error(
                validate_power_params_fips, "apc", {}
            )
            self.assertIsNotNone(exc)
            self.assertEqual("fips_violation", exc.code)

    def test_accepts_compliant_driver_in_fips(self):
        """A compliant driver with correct cipher does not raise."""
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            # Should not raise
            validate_power_params_fips("ipmi", {"cipher_suite_id": "17"})

    def test_rejects_ipmi_non_fips_cipher(self):
        """IPMI with a non-FIPS cipher raises ValidationError with fips_violation."""
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            exc = _raises_validation_error(
                validate_power_params_fips, "ipmi", {"cipher_suite_id": "3"}
            )
            self.assertIsNotNone(exc)
            self.assertEqual("fips_violation", exc.code)

    def test_rejects_webhook_ssl_disabled(self):
        """webhook with verify_ssl=False raises ValidationError in FIPS mode."""
        with patch(
            "maasserver.forms.fips_power.is_fips_enabled", return_value=True
        ):
            exc = _raises_validation_error(
                validate_power_params_fips, "webhook", {"verify_ssl": False}
            )
            self.assertIsNotNone(exc)
            self.assertEqual("fips_violation", exc.code)


class TestValidatePowerPassComplexity(MAASTestCase):
    def _patch(self, active):
        return patch(
            "maasserver.forms.fips_power.is_hardening_enabled",
            return_value=active,
        )

    def test_noop_when_hardening_inactive(self):
        """When hardening is not active, weak passwords are accepted."""
        with self._patch(False):
            validate_power_pass_complexity({"power_pass": "weak"})

    def test_rejects_weak_password_when_hardening(self):
        """A weak password raises ValidationError with code password_complexity."""
        with self._patch(True):
            exc = _raises_validation_error(
                validate_power_pass_complexity, {"power_pass": "weak"}
            )
        self.assertIsNotNone(exc)
        self.assertEqual("password_complexity", exc.code)

    def test_accepts_strong_password(self):
        """A password meeting all complexity rules does not raise."""
        with self._patch(True):
            validate_power_pass_complexity({"power_pass": "Str0ng!Pass#2026"})

    def test_skips_empty_password(self):
        """Empty power_pass is skipped even when hardening is active."""
        with self._patch(True):
            validate_power_pass_complexity({"power_pass": ""})
