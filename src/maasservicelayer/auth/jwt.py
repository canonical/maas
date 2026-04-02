#  Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any, cast, Self

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jws import JWSRegistry
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

from maasservicelayer.auth.time import utc_from_timestamp
from maasservicelayer.utils.date import utcnow


class InvalidToken(Exception):
    """Token is invalid"""


@dataclass(frozen=True)
class JWT:
    TOKEN_ALGORITHM = "HS256"
    TOKEN_DURATION = timedelta(minutes=10)

    AUDIENCE = "api"
    ISSUER = "MAAS"

    payload: dict[str, Any]
    encoded: str

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
    def user_id(self) -> int:
        return self.payload["user_id"]

    @classmethod
    def create(cls, key: str, subject: str, user_id: int) -> Self:
        issued = utcnow()
        expiration = issued + cls.TOKEN_DURATION

        payload = {
            "sub": subject,
            "iss": cls.ISSUER,
            "iat": issued.timestamp(),
            "exp": expiration.timestamp(),
            "aud": cls.AUDIENCE,
            # private claims
            "user_id": user_id,
        }
        key_obj = OctKey.import_key(key)
        encoded = jwt.encode({"alg": cls.TOKEN_ALGORITHM}, payload, key_obj)
        return cls(
            payload=payload,
            encoded=encoded,
        )

    @classmethod
    def decode(cls, key: str, encoded: str) -> Self:
        """Decode a token string."""
        try:
            key_obj = OctKey.import_key(key)
            jws_reg = JWSRegistry(algorithms=[cls.TOKEN_ALGORITHM])
            token = jwt.decode(encoded, key_obj, registry=jws_reg)
            claims_reg = JWTClaimsRegistry(
                iss={"essential": True, "value": cls.ISSUER},
                aud={"essential": True, "value": cls.AUDIENCE},
                exp={"essential": True},
                sub={"essential": True, "allow_blank": True},
                iat={"essential": True},
                leeway=120,
            )
            claims_reg.validate(token.claims)
            payload = token.claims
        except (JoseError, KeyError, ValueError):
            raise InvalidToken()  # noqa: B904

        return cls(
            payload=payload,
            encoded=encoded,
        )
