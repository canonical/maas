# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootSourceTable
from maasservicelayer.models.bootsources import BootSource


class BootSourcesClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(BootSourceTable.c.id, id))

    @classmethod
    def with_url(cls, url: str) -> Clause:
        return Clause(condition=eq(BootSourceTable.c.url, url))

    @classmethod
    def with_ids(cls, ids: set[int]) -> Clause:
        return Clause(condition=BootSourceTable.c.id.in_(ids))


class BootSourcesRepository(BaseRepository[BootSource]):
    def get_repository_table(self) -> Table:
        return BootSourceTable

    def get_model_factory(self) -> type[BootSource]:
        return BootSource
