#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with JWT tokens."""

import json
import time
from typing import Any

from joserfc import jws
from joserfc.errors import JoseError


class JWTDecodeError(Exception):
    """Exception raised when JWT decoding or validation fails."""


class JWTExpiredError(JWTDecodeError):
    """Exception raised when a JWT token has expired."""


class JWTInvalidError(JWTDecodeError):
    """Exception raised when a JWT token is invalid."""


class JWTAudienceError(JWTDecodeError):
    """Exception raised when JWT audience validation fails."""


def decode_unverified_jwt(
    token: str,
    check_expiration: bool = True,
    expected_audience: str | None = None,
) -> dict[str, Any]:
    """Decode a JWT without verifying its signature to extract claims."""
    try:
        token_bytes = token.encode("utf-8")
        compact_sig = jws.extract_compact(token_bytes)
        claims = json.loads(compact_sig.payload.decode("utf-8"))

        if check_expiration and "exp" in claims:
            if time.time() > claims["exp"]:
                raise JWTExpiredError("token is expired")

        if expected_audience is not None:
            aud = claims.get("aud")
            throw = False
            match aud:
                case str():
                    throw = aud != expected_audience
                case list():
                    throw = expected_audience not in aud
                case None:
                    throw = True
            if throw:
                raise JWTAudienceError(
                    f"invalid audience: expected {expected_audience}, got {aud}"
                )
        return claims

    except (
        JoseError,
        ValueError,
        json.JSONDecodeError,
        KeyError,
        AttributeError,
        TypeError,
    ) as ex:
        raise JWTInvalidError(f"invalid JWT: {str(ex)}") from ex
