#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DNSDataTable
from maasservicelayer.models.dnsdata import DNSData


class DNSDataClauseFactory(ClauseFactory):
    @classmethod
    def with_dnsresource_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DNSDataTable.c.dnsresource_id, id))

    @classmethod
    def with_rrtype(cls, rrtype: DNSResourceTypeEnum) -> Clause:
        return Clause(condition=eq(DNSDataTable.c.rrtype, rrtype))


class DNSDataRepository(BaseRepository[DNSData]):
    def get_repository_table(self) -> Table:
        return DNSDataTable

    def get_model_factory(self) -> Type[DNSData]:
        return DNSData
