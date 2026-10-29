#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.dnsresources import DNSResource


class DNSResourceFilters(FilterFactory):
    model = DNSResource

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_name(cls, name: str) -> FieldFilter:
        return cls._equals("name", name)

    @classmethod
    def with_domain_id(cls, id: int) -> FieldFilter:
        return cls._equals("domain_id", id)
