# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DHCPSnippetTable
from maasservicelayer.models.dhcpsnippets import DhcpSnippet


class DhcpSnippetsClauseFactory(ClauseFactory):
    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(DHCPSnippetTable.c.subnet_id, subnet_id))

    @classmethod
    def with_iprange_id(cls, iprange_id: int) -> Clause:
        return Clause(condition=eq(DHCPSnippetTable.c.iprange_id, iprange_id))


class DhcpSnippetsRepository(BaseRepository[DhcpSnippet]):
    def get_repository_table(self) -> Table:
        return DHCPSnippetTable

    def get_model_factory(self) -> Type[DhcpSnippet]:
        return DhcpSnippet
