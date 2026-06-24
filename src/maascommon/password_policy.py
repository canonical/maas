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

    Enforces: min 14 chars, uppercase, digit, special char.

    The 14-character floor also satisfies the FIPS lower bound on PBKDF2/HMAC
    key length (112 bits = 14 bytes): Django's PBKDF2 hasher feeds the password
    in as the HMAC key, and OpenSSL's FIPS provider rejects keys shorter than
    14 bytes with "[Provider routines] invalid key length". A 14-character
    password is >= 14 bytes for any encoding, so hashing never trips that error.

    Only call this when hardening is active.
    """
    errors: list[str] = []

    if len(password) < 14:
        errors.append("Password must be at least 14 characters")
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


def enforce_password_complexity(password: str) -> None:
    """Raise ``ValueError`` when hardening is active and ``password`` is weak.

    "Active" means either: (a) ``configure_hardening()`` was called and set the
    process-wide flag, or (b) the kernel reports FIPS mode directly via
    ``/proc/sys/crypto/fips_enabled``.  The second check ensures that CLI
    management commands (e.g. ``createadmin``, ``changepassword``) — which run
    as short-lived subprocesses and never reach the region service startup that
    calls ``configure_hardening()`` — still enforce the policy on a FIPS host.

    No-op when neither condition is true.  The raised message joins every policy
    violation with ``"; "`` so a single error surfaces all missing criteria.
    """
    from maascommon.fips import is_fips_enabled
    from maascommon.hardening import is_hardening_enabled

    if not (is_hardening_enabled() or is_fips_enabled()):
        return
    result = validate_password_complexity(password)
    if not result.is_valid:
        raise ValueError("; ".join(result.errors))
