#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import cached_property
from typing import Any, cast, Sequence

from jose import jwt, JWTError

from maasservicelayer.auth.time import utc_from_timestamp


class InvalidToken(Exception):
    """Token is invalid"""


class UserRole(str, Enum):
    """Valid values for token audience."""

    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True)
class JWT:
    TOKEN_ALGORITHM = "HS256"
    TOKEN_DURATION = timedelta(minutes=10)

    AUDIENCE = "api"
    ISSUER = "MAAS"

    payload: dict[str, Any]
    encoded: str

    _REQUIRED_FIELDS: frozenset[str] = frozenset(
        ("aud", "iat", "iss", "exp", "sub")
    )

    @cached_property
    def issuer(self) -> str:
        return cast(str, self.payload["iss"])

    @cached_property
    def subject(self) -> str:
        return cast(str, self.payload["sub"])

    @cached_property
    def issued(self) -> datetime:
        return utc_from_timestamp(self.payload["iat"])

    @cached_property
    def expiration(self) -> datetime:
        return utc_from_timestamp(self.payload["exp"])

    @cached_property
    def audience(self) -> list[str]:
        return self.payload["aud"]

    @cached_property
    def roles(self) -> list[UserRole]:
        return self.payload["roles"]

    @classmethod
    def create(
        cls, key: str, subject: str, roles: Sequence[UserRole]
    ) -> "JWT":
        issued = datetime.now(timezone.utc)
        expiration = issued + cls.TOKEN_DURATION

        payload = {
            "sub": subject,
            "iss": cls.ISSUER,
            "iat": issued.timestamp(),
            "exp": expiration.timestamp(),
            "aud": cls.AUDIENCE,
            # private claims
            "roles": roles,
        }
        encoded = jwt.encode(payload, key, algorithm=cls.TOKEN_ALGORITHM)
        return cls(
            payload=payload,
            encoded=encoded,
        )

    @classmethod
    def decode(cls, key: str, encoded: str) -> "JWT":
        """Decode a token string."""
        try:
            payload = jwt.decode(
                encoded,
                key,
                algorithms=[cls.TOKEN_ALGORITHM],
                issuer=cls.ISSUER,
                audience=cls.AUDIENCE,
            )
        except JWTError:
            raise InvalidToken()

        # check that all required fields are there
        if cls._REQUIRED_FIELDS - set(payload):
            raise InvalidToken()

        token = cls(
            payload=payload,
            encoded=encoded,
        )

        return token
