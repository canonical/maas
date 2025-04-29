# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import RDNSTable
from maasservicelayer.models.rdns import RDNS


class RDNSClauseFactory(ClauseFactory):
    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address):
        return Clause(condition=eq(RDNSTable.c.ip, ip))


class RDNSRepository(BaseRepository[RDNS]):
    def get_repository_table(self) -> Table:
        return RDNSTable

    def get_model_factory(self) -> type[RDNS]:
        return RDNS
