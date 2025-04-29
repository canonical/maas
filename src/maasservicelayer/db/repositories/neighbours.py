#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NeighbourTable
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.neighbours import Neighbour


class NeighbourClauseFactory(ClauseFactory):
    @classmethod
    def with_ip(cls, ip: IPv4Address | IPv6Address):
        return Clause(condition=eq(NeighbourTable.c.ip, ip))

    @classmethod
    def with_mac(cls, mac: MacAddress):
        return Clause(condition=eq(NeighbourTable.c.mac_address, mac))


class NeighboursRepository(BaseRepository[Neighbour]):
    def get_repository_table(self) -> Table:
        return NeighbourTable

    def get_model_factory(self) -> type[Neighbour]:
        return Neighbour
