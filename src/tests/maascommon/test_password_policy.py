#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.password_policy import validate_password_complexity


class TestValidatePasswordComplexity:
    def test_valid_password(self) -> None:
        result = validate_password_complexity("Str0ng!Pass#1")
        assert result.is_valid
        assert result.errors == []

    def test_too_short(self) -> None:
        result = validate_password_complexity("Sh0rt!")
        assert not result.is_valid
        assert any("12 characters" in e for e in result.errors)

    def test_no_uppercase(self) -> None:
        # 10 chars — also fails length, but let's test with long enough
        result2 = validate_password_complexity("weakpassword1!")
        assert not result2.is_valid
        assert any("uppercase" in e for e in result2.errors)

    def test_no_digit(self) -> None:
        result = validate_password_complexity("StrongPass!!")
        assert not result.is_valid
        assert any("digit" in e for e in result.errors)

    def test_no_special_char(self) -> None:
        result = validate_password_complexity("StrongPass12")
        assert not result.is_valid
        assert any("special" in e for e in result.errors)

    def test_dash_counts_as_special(self) -> None:
        """'-' is a valid special character (was excluded by old regex)."""
        result = validate_password_complexity("StrongPass-12")
        assert result.is_valid

    def test_underscore_counts_as_special(self) -> None:
        """'_' is a valid special character (was excluded by old regex)."""
        result = validate_password_complexity("StrongPass_12")
        assert result.is_valid

    def test_space_counts_as_special(self) -> None:
        """Space is a valid special character (NIST allows it)."""
        result = validate_password_complexity("StrongPass 12")
        assert result.is_valid

    def test_multiple_failures(self) -> None:
        result = validate_password_complexity("short")
        assert not result.is_valid
        assert len(result.errors) >= 3
