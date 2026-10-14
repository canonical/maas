#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""FIPS-compliant password generation utilities."""

from base64 import b64encode
from os import urandom
import random
import secrets
import string

from maascommon.password_policy import validate_password_complexity


def _generate_password_by_rule(length: int) -> str:
    """Generate a password guaranteed to satisfy the complexity policy.

    Unlike random sampling, this forces one uppercase letter, one digit, and
    one special character into fixed draws before filling the remaining
    positions and shuffling. This trades a small amount of distribution
    uniformity for a guaranteed-terminating construction, used as a fallback
    when random sampling fails to find a compliant result within a bounded
    number of attempts.
    """
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    # Matches the altchars used by the base64-based candidate generator.
    special = ".!"

    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    all_chars = uppercase + lowercase + digits + special
    password_chars += [
        secrets.choice(all_chars) for _ in range(length - len(password_chars))
    ]

    rng = random.SystemRandom()
    rng.shuffle(password_chars)

    return "".join(password_chars)


def _generate_base64_password(length: int) -> str:
    """Generate a candidate password by base64-encoding random bytes.

    Uses `.` and `!` in place of the standard `+`/`/` altchars, so the
    output alphabet is limited to letters, digits, `.`, and `!`.

    Requests enough random bytes, rounded up to a multiple of 3, so the
    base64 encoding never produces padding (`=`) characters; every
    character considered is genuinely random rather than a fixed filler.
    """
    num_groups = -(-length // 4)  # ceil(length / 4)
    num_bytes = num_groups * 3
    encoded = b64encode(urandom(num_bytes), altchars=b".!").decode("ascii")
    return encoded[:length]


def generate_password(length: int = 14, max_attempts: int = 100) -> str:
    """Generate a FIPS-compliant password.

    Generates a password meeting FIPS 140-2/140-3 and STIG/CIS hardening
    requirements, as enforced by `validate_password_complexity`:
    - Minimum 14 characters (satisfies FIPS lower bound on PBKDF2/HMAC key length)
    - At least one uppercase letter
    - At least one digit
    - At least one special character (non-alphanumeric)

    Generates candidates by base64-encoding random bytes and retries until
    one satisfies the complexity policy. If no compliant password is found
    within `max_attempts`, falls back to a rule-based construction that is
    guaranteed to satisfy the policy.

    Args:
        length: Desired password length (minimum 14). Defaults to 14.
        max_attempts: Maximum candidates to try before falling back to the
            rule-based construction. Defaults to 100.

    Raises:
        ValueError: If length is less than 14.

    Returns:
        A FIPS-compliant password string.
    """
    if length < 14:
        raise ValueError(
            f"Password length must be at least 14 characters, got {length}"
        )

    for _ in range(max_attempts):
        password = _generate_base64_password(length)
        if validate_password_complexity(password).is_valid:
            return password

    return _generate_password_by_rule(length)
