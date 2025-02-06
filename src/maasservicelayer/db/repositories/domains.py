#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import select, Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DomainTable, GlobalDefaultTable
from maasservicelayer.models.domains import Domain


class DomainsClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DomainTable.c.id, id))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(DomainTable.c.name, name))

    @classmethod
    def with_authoritative(cls, authoritative: bool) -> Clause:
        return Clause(condition=eq(DomainTable.c.authoritative, authoritative))

    @classmethod
    def with_ttl(cls, ttl: int) -> Clause:
        return Clause(condition=eq(DomainTable.c.ttl, ttl))


class DomainsRepository(BaseRepository[Domain]):
    def get_repository_table(self) -> Table:
        return DomainTable

    def get_model_factory(self) -> Type[Domain]:
        return Domain

    async def get_default_domain(self) -> Domain:
        stmt = (
            select(DomainTable)
            .select_from(GlobalDefaultTable)
            .join(
                DomainTable, DomainTable.c.id == GlobalDefaultTable.c.domain_id
            )
            .filter(GlobalDefaultTable.c.id == 0)
        )

        default_domain = (await self.execute_stmt(stmt)).one()

        return Domain(**default_domain._asdict())
