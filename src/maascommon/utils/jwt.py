#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with JWT tokens."""

import base64
import json
import time
from typing import Any


class JWTDecodeError(Exception):
    """Exception raised when JWT decoding or validation fails."""


def decode_unverified_jwt(
    token: str,
    check_expiration: bool = True,
    expected_audience: str | None = None,
) -> dict[str, Any]:
    """
    Decode a JWT without signature verification to extract claims.

    This is useful when you need to read JWT claims before verification
    or when verification isn't required (e.g., public information).

    Args:
        token: JWT token string
        check_expiration: Whether to validate the expiration claim
        expected_audience: Optional audience to validate against

    Returns:
        The decoded JWT claims as a dictionary

    Raises:
        JWTDecodeError: If the token is invalid, expired, or audience doesn't match
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise JWTDecodeError("invalid JWT format")

        payload_part = parts[1]
        payload_part += "=" * (4 - len(payload_part) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_part))

        if check_expiration and "exp" in claims:
            if time.time() > claims["exp"]:
                raise JWTDecodeError("token is expired")

        if expected_audience is not None:
            aud = claims.get("aud")
            if aud != expected_audience:
                raise JWTDecodeError(
                    f"invalid audience: expected {expected_audience}, got {aud}"
                )

        return claims

    except (ValueError, json.JSONDecodeError, KeyError) as ex:
        raise JWTDecodeError(f"invalid JWT: {str(ex)}") from ex
