#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Type

from sqlalchemy import select, Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import DomainTable, GlobalDefaultTable
from maasservicelayer.models.domains import Domain


class DomainsClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(DomainTable.c.id, id))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(DomainTable.c.name, name))


class DomainResourceBuilder(ResourceBuilder):
    def with_authoritative(
        self, authoritative: bool
    ) -> "DomainResourceBuilder":
        self._request.set_value(
            DomainTable.c.authoritative.name, authoritative
        )
        return self

    def with_ttl(self, ttl: int) -> "DomainResourceBuilder":
        self._request.set_value(DomainTable.c.ttl.name, ttl)
        return self

    def with_name(self, name: str) -> "DomainResourceBuilder":
        self._request.set_value(DomainTable.c.name.name, name)
        return self


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

        default_domain = (await self.connection.execute(stmt)).one()

        return Domain(**default_domain._asdict())
