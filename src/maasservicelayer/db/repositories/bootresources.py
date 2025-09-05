# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import case, Table

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.db.filters import (
    Clause,
    ClauseFactory,
    OrderByClause,
    OrderByClauseFactory,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceTable
from maasservicelayer.models.bootresources import BootResource


class BootResourceClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.name, name))

    @classmethod
    def with_names(cls, names: list[str]) -> Clause:
        return Clause(condition=BootResourceTable.c.name.in_(names))

    @classmethod
    def with_architecture(cls, architecture: str) -> Clause:
        return Clause(
            condition=eq(BootResourceTable.c.architecture, architecture)
        )

    @classmethod
    def with_architecture_starting_with(cls, partial_arch: str) -> Clause:
        return Clause(
            condition=BootResourceTable.c.architecture.startswith(partial_arch)
        )

    @classmethod
    def with_alias(cls, alias: str | None) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.alias, alias))

    @classmethod
    def with_rtype(cls, rtype: BootResourceType) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.rtype, rtype))

    @classmethod
    def with_ids(cls, ids: set[int]) -> Clause:
        return Clause(condition=BootResourceTable.c.id.in_(ids))


class BootResourceOrderByClauses(OrderByClauseFactory):
    @staticmethod
    def by_name_with_priority(lts_releases: list[str]) -> OrderByClause:
        return OrderByClause(
            column=case(
                {
                    release: priority
                    for priority, release in enumerate(lts_releases)
                },
                value=BootResourceTable.c.name,
            )
        )


class BootResourcesRepository(BaseRepository[BootResource]):
    def get_repository_table(self) -> Table:
        return BootResourceTable

    def get_model_factory(self) -> type[BootResource]:
        return BootResource
