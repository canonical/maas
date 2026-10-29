#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import DNSDataTable, DNSResourceTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.dnsdata import (
    DNSDataInDomain,
    DNSDataStartingWith,
    DNSDataWithResourceName,
)
from maasservicelayer.models.dnsdata import DNSData


class DNSDataDomainDataMapper(DefaultDomainDataMapper[DNSData]):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case DNSDataStartingWith(partial_rrdata):
                return Clause(
                    condition=DNSDataTable.c.rrdata.startswith(partial_rrdata)
                )
            case DNSDataWithResourceName(name):
                condition = DNSResourceTable.c.name == name
            case DNSDataInDomain(domain_id):
                condition = DNSResourceTable.c.domain_id == domain_id
            case _:
                return super().custom_filter_clause(filter)
        return Clause(
            condition=condition,
            joins=[
                join(
                    DNSResourceTable,
                    DNSDataTable,
                    DNSResourceTable.c.id == DNSDataTable.c.dnsresource_id,
                )
            ],
        )
