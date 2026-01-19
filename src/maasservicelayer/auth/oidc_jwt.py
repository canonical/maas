#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from functools import cached_property
from typing import Self

from authlib.jose import jwt, JWTClaims, KeySet
from authlib.jose.errors import DecodeError, InvalidClaimError

from maasservicelayer.models.external_auth import OAuthProvider


class JWTDecodeException(Exception):
    """JWT decoding failed"""


class JWTValidationException(Exception):
    """JWT validation failed"""


@dataclass(frozen=True)
class BaseOAuthToken:
    TOKEN_ALGORITHM = "RS256"

    claims: JWTClaims
    encoded: str
    provider: OAuthProvider

    _REQUIRED_FIELDS: frozenset[str] = frozenset(
        ("aud", "iss", "sub", "exp", "iat")
    )

    @cached_property
    def issuer(self) -> str:
        return self.claims["iss"].rstrip("/")

    @cached_property
    def audience(self) -> list[str]:
        aud = self.claims["aud"]
        return aud if isinstance(aud, list) else [aud]

    @cached_property
    def email(self) -> str:
        return self.claims["email"]

    @classmethod
    def from_token(
        cls,
        provider: OAuthProvider,
        encoded: str,
        jwks: KeySet,
        nonce: str | None = None,
        skip_validation: bool = False,
    ) -> Self:
        try:
            claims = jwt.decode(encoded, jwks)
        except DecodeError as e:
            raise JWTDecodeException() from e

        token = cls(claims=claims, encoded=encoded, provider=provider)
        if skip_validation:
            return token
        token.validate(nonce=nonce)

        return token

    def validate(self, **kwargs) -> None:
        """Base validation of the token claims."""
        if self._REQUIRED_FIELDS - set(self.claims) or (
            self.issuer != self.provider.issuer_url
        ):
            raise JWTValidationException()

        try:
            self.claims.validate()
        except InvalidClaimError as e:
            raise JWTValidationException() from e


@dataclass(frozen=True)
class OAuthAccessToken(BaseOAuthToken):
    pass


@dataclass(frozen=True)
class OAuthIDToken(BaseOAuthToken):
    def validate(self, *, nonce: str, **kwargs) -> None:
        super().validate()
        alg = self.claims.header.get("alg")
        azp = self.claims.get("azp")
        if (
            alg != self.TOKEN_ALGORITHM
            or (azp is not None and azp != self.provider.client_id)
            or (self.claims.get("nonce") != nonce)
            or (self.provider.client_id not in self.audience)
        ):
            raise JWTValidationException()
