#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.dnsdata import DNSData


@dataclass(frozen=True)
class DNSDataStartingWith(CustomFilter):
    model: ClassVar[type[DNSData]] = DNSData
    partial_rrdata: str


@dataclass(frozen=True)
class DNSDataWithResourceName(CustomFilter):
    model: ClassVar[type[DNSData]] = DNSData
    name: str


@dataclass(frozen=True)
class DNSDataInDomain(CustomFilter):
    model: ClassVar[type[DNSData]] = DNSData
    domain_id: int


class DNSDataFilters(FilterFactory):
    model = DNSData

    @classmethod
    def with_dnsresource_id(cls, id: int) -> FieldFilter:
        return cls._equals("dnsresource_id", id)

    @classmethod
    def with_rrtype(cls, rrtype: DNSResourceTypeEnum) -> FieldFilter:
        return cls._equals("rrtype", rrtype)

    @classmethod
    def with_rrdata_starting_with(
        cls, partial_rrdata: str
    ) -> DNSDataStartingWith:
        return DNSDataStartingWith(partial_rrdata)

    @classmethod
    def with_dnsresource_name(cls, name: str) -> DNSDataWithResourceName:
        return DNSDataWithResourceName(name)

    @classmethod
    def with_domain_id(cls, domain_id: int) -> DNSDataInDomain:
        return DNSDataInDomain(domain_id)
