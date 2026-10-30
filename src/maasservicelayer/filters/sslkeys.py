# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.sslkeys import SSLKey


class SSLKeyFilters(FilterFactory):
    model = SSLKey

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_user_id(cls, user_id: int) -> FieldFilter:
        return cls._equals("user_id", user_id)

    @classmethod
    def with_key(cls, key: str) -> FieldFilter:
        return cls._equals("key", key)
