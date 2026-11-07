# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import Filter, FilterFactory
from maasservicelayer.models.consumers import Consumer


class ConsumerFilters(FilterFactory):
    model = Consumer

    @classmethod
    def with_user_id(cls, user_id: int) -> Filter:
        return cls._equals("user_id", user_id)

    @classmethod
    def with_secret(cls, secret: str) -> Filter:
        return cls._equals("secret", secret)

    @classmethod
    def with_key(cls, key: str) -> Filter:
        return cls._equals("key", key)
