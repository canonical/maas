#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Password and credential complexity validators for MAAS hardening."""

from dataclasses import dataclass, field
import re


@dataclass
class PasswordValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def validate_password_complexity(password: str) -> PasswordValidationResult:
    """Validate password complexity requirements for hardening mode.

    Enforces: min 12 chars, uppercase, digit, special char.
    Only call this when hardening is active.
    """
    errors: list[str] = []

    if len(password) < 12:
        errors.append("Password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[^a-zA-Z0-9]", password):
        errors.append(
            "Password must contain at least one special character"
            " (any non-alphanumeric character)"
        )

    return PasswordValidationResult(is_valid=len(errors) == 0, errors=errors)
