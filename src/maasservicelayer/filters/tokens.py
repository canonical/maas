# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import Filter, FilterFactory
from maasservicelayer.models.tokens import (
    OIDCRevokedToken,
    RefreshToken,
    Token,
)


class TokenFilters(FilterFactory):
    model = Token

    @classmethod
    def with_consumer_id(cls, consumer_id: int) -> Filter:
        return cls._equals("consumer_id", consumer_id)

    @classmethod
    def with_consumer_ids(cls, ids: list[int]) -> Filter:
        return cls._is_in("consumer_id", ids)

    @classmethod
    def with_secret(cls, secret: str) -> Filter:
        return cls._equals("secret", secret)

    @classmethod
    def with_key(cls, key: str) -> Filter:
        return cls._equals("key", key)


class RefreshTokenFilters(FilterFactory):
    model = RefreshToken

    @classmethod
    def with_token(cls, token: str) -> Filter:
        return cls._equals("token", token)


class OIDCRevokedTokenFilters(FilterFactory):
    model = OIDCRevokedToken

    @classmethod
    def with_token_hash(cls, token_hash: str) -> Filter:
        return cls._equals("token_hash", token_hash)
