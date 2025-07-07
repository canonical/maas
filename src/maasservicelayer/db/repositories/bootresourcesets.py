# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceSetTable
from maasservicelayer.models.bootresourcesets import BootResourceSet


class BootResourceSetClauseFactory(ClauseFactory):
    @classmethod
    def with_resource_id(cls, resource_id: int) -> Clause:
        return Clause(
            condition=eq(BootResourceSetTable.c.resource_id, resource_id)
        )

    @classmethod
    def with_version(cls, version: str) -> Clause:
        return Clause(condition=eq(BootResourceSetTable.c.version, version))


class BootResourceSetsRepository(BaseRepository[BootResourceSet]):
    def get_repository_table(self) -> Table:
        return BootResourceSetTable

    def get_model_factory(self) -> type[BootResourceSet]:
        return BootResourceSet
