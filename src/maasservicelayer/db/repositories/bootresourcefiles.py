# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceFileTable
from maasservicelayer.models.bootresourcefiles import BootResourceFile


class BootResourceFileClauseFactory(ClauseFactory):
    @classmethod
    def with_sha256_starting_with(cls, partial_sha256: str) -> Clause:
        return Clause(
            condition=BootResourceFileTable.c.sha256.startswith(partial_sha256)
        )

    @classmethod
    def with_sha256(cls, sha256: str) -> Clause:
        return Clause(condition=eq(BootResourceFileTable.c.sha256, sha256))


class BootResourceFilesRepository(BaseRepository[BootResourceFile]):
    def get_repository_table(self) -> Table:
        return BootResourceFileTable

    def get_model_factory(self) -> type[BootResourceFile]:
        return BootResourceFile
