# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceTable
from maasservicelayer.models.bootresources import BootResource


class BootResourceClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.name, name))

    @classmethod
    def with_architecture(cls, architecture: str) -> Clause:
        return Clause(
            condition=eq(BootResourceTable.c.architecture, architecture)
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


class BootResourcesRepository(BaseRepository[BootResource]):
    def get_repository_table(self) -> Table:
        return BootResourceTable

    def get_model_factory(self) -> type[BootResource]:
        return BootResource
