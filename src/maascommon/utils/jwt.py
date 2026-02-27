#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with JWT tokens."""

import json
import time
from typing import Any

from joserfc import jws
from joserfc.errors import JoseError


class JWTDecodeError(Exception):
    """Exception raised when JWT decoding or validation fails."""


def decode_unverified_jwt(
    token: str,
    check_expiration: bool = True,
    expected_audience: str | None = None,
) -> dict[str, Any]:
    """
    Decode a JWT without signature verification to extract claims.

    This function uses joserfc.jws.extract_compact to safely extract
    JWT claims without validating the signature. This is useful when
    you need to read JWT claims before verification (e.g., to determine
    the issuer) or when verification isn't required.

    Args:
        token: JWT token string
        check_expiration: Whether to validate the expiration claim
        expected_audience: Optional audience to validate against

    Returns:
        The decoded JWT claims as a dictionary

    Raises:
        JWTDecodeError: If the token is invalid, expired, or audience doesn't match

    Example:
        >>> token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        >>> claims = decode_unverified_jwt(token, check_expiration=False)
        >>> issuer = claims.get("iss")
    """
    try:
        # Use joserfc to safely extract JWT components without verification
        token_bytes = token.encode("utf-8")
        compact_sig = jws.extract_compact(token_bytes)

        # Decode the payload to get claims
        claims = json.loads(compact_sig.payload.decode("utf-8"))

        # Validate expiration if requested
        if check_expiration and "exp" in claims:
            if time.time() > claims["exp"]:
                raise JWTDecodeError("token is expired")

        # Validate audience if requested
        if expected_audience is not None:
            aud = claims.get("aud")
            if aud != expected_audience:
                raise JWTDecodeError(
                    f"invalid audience: expected {expected_audience}, got {aud}"
                )

        return claims

    except (
        JoseError,
        ValueError,
        json.JSONDecodeError,
        KeyError,
        AttributeError,
    ) as ex:
        raise JWTDecodeError(f"invalid JWT: {str(ex)}") from ex
