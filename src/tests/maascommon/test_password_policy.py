#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

import maascommon.hardening as H
from maascommon.password_policy import (
    enforce_password_complexity,
    validate_password_complexity,
)


@pytest.fixture(autouse=True)
def reset_hardening():
    """Restore the process-wide hardening globals after every test."""
    original_active = H._hardening_active
    original_configured = H._hardening_configured
    yield
    H._hardening_active = original_active
    H._hardening_configured = original_configured


class TestValidatePasswordComplexity:
    def test_valid_password(self) -> None:
        # 14 chars, has uppercase, digit and special.
        result = validate_password_complexity("Str0ng!Pass#12")
        assert result.is_valid
        assert result.errors == []

    def test_too_short(self) -> None:
        result = validate_password_complexity("Sh0rt!")
        assert not result.is_valid
        assert any("14 characters" in e for e in result.errors)

    def test_no_uppercase(self) -> None:
        # >= 14 chars so only the uppercase rule is violated.
        result = validate_password_complexity("weakpassword1!")
        assert not result.is_valid
        assert any("uppercase" in e for e in result.errors)

    def test_no_digit(self) -> None:
        # >= 14 chars, has upper + special, missing only a digit.
        result = validate_password_complexity("StrongPassword!!")
        assert not result.is_valid
        assert any("digit" in e for e in result.errors)

    def test_no_special_char(self) -> None:
        # >= 14 chars, has upper + digit, missing only a special char.
        result = validate_password_complexity("StrongPass1234")
        assert not result.is_valid
        assert any("special" in e for e in result.errors)

    def test_dash_counts_as_special(self) -> None:
        """'-' is a valid special character (was excluded by old regex)."""
        result = validate_password_complexity("StrongPass-123")
        assert result.is_valid

    def test_underscore_counts_as_special(self) -> None:
        """'_' is a valid special character (was excluded by old regex)."""
        result = validate_password_complexity("StrongPass_123")
        assert result.is_valid

    def test_space_counts_as_special(self) -> None:
        """Space is a valid special character (NIST allows it)."""
        result = validate_password_complexity("StrongPass 123")
        assert result.is_valid

    def test_multiple_failures(self) -> None:
        result = validate_password_complexity("short")
        assert not result.is_valid
        assert len(result.errors) >= 3

    def test_thirteen_chars_rejected_for_length(self) -> None:
        # Otherwise compliant (upper + digit + special) but one char short of
        # the 14 floor: proves 14 is the boundary.
        password = "Str0ng!Pass#1"
        assert len(password) == 13
        result = validate_password_complexity(password)
        assert not result.is_valid
        assert any("14 characters" in e for e in result.errors)

    def test_fourteen_chars_accepted(self) -> None:
        # Exactly at the 14 floor with all classes present.
        password = "Str0ng!Pass#12"
        assert len(password) == 14
        result = validate_password_complexity(password)
        assert result.is_valid
        assert result.errors == []


class TestEnforcePasswordComplexity:
    def test_no_raise_when_hardening_inactive(self) -> None:
        H._hardening_active = False
        H._hardening_configured = True
        # A weak password is tolerated when hardening is off.
        assert enforce_password_complexity("secret") is None

    def test_raises_when_hardening_active_and_weak(self) -> None:
        H._hardening_active = True
        H._hardening_configured = True
        with pytest.raises(ValueError) as exc_info:
            enforce_password_complexity("secret")
        assert "at least 14 characters" in str(exc_info.value)

    def test_no_raise_when_hardening_active_and_compliant(self) -> None:
        H._hardening_active = True
        H._hardening_configured = True
        assert enforce_password_complexity("Str0ng!Pass#12") is None
