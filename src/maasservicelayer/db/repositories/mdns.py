# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import MDNSTable
from maasservicelayer.models.mdns import MDNS


class MDNSClauseFactory(ClauseFactory):
    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address):
        return Clause(condition=eq(MDNSTable.c.ip, ip))


class MDNSRepository(BaseRepository[MDNS]):
    def get_repository_table(self) -> Table:
        return MDNSTable

    def get_model_factory(self) -> type[MDNS]:
        return MDNS
