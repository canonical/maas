#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import join, Table
from sqlalchemy.sql.operators import eq

from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DNSDataTable, DNSResourceTable
from maasservicelayer.models.dnsdata import DNSData


class DNSDataClauseFactory(ClauseFactory):
    @classmethod
    def with_dnsresource_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DNSDataTable.c.dnsresource_id, id))

    @classmethod
    def with_rrtype(cls, rrtype: DNSResourceTypeEnum) -> Clause:
        return Clause(condition=eq(DNSDataTable.c.rrtype, rrtype))

    @classmethod
    def with_rrdata_starting_with(cls, partial_rrdata: str) -> Clause:
        return Clause(
            condition=DNSDataTable.c.rrdata.startswith(partial_rrdata)
        )

    @classmethod
    def with_dnsresource_name(cls, name: str) -> Clause:
        return Clause(
            condition=eq(DNSResourceTable.c.name, name),
            joins=[
                join(
                    DNSResourceTable,
                    DNSDataTable,
                    eq(DNSResourceTable.c.id, DNSDataTable.c.dnsresource_id),
                ),
            ],
        )

    @classmethod
    def with_domain_id(cls, domain_id: int) -> Clause:
        return Clause(
            condition=eq(DNSResourceTable.c.domain_id, domain_id),
            joins=[
                join(
                    DNSResourceTable,
                    DNSDataTable,
                    eq(DNSResourceTable.c.id, DNSDataTable.c.dnsresource_id),
                ),
            ],
        )


class DNSDataRepository(BaseRepository[DNSData]):
    def get_repository_table(self) -> Table:
        return DNSDataTable

    def get_model_factory(self) -> Type[DNSData]:
        return DNSData
