#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.domains import Domain


class DomainsFilters(FilterFactory):
    model = Domain

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_name(cls, name: str) -> FieldFilter:
        return cls._equals("name", name)

    @classmethod
    def with_authoritative(cls, authoritative: bool) -> FieldFilter:
        return cls._equals("authoritative", authoritative)

    @classmethod
    def with_ttl(cls, ttl: int) -> FieldFilter:
        return cls._equals("ttl", ttl)
