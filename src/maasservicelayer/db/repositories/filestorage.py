#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import FileStorageTable
from maasservicelayer.models.filestorage import FileStorage


class FileStorageClauseFactory(ClauseFactory):
    @classmethod
    def with_owner_id(cls, owner_id: int) -> Clause:
        return Clause(condition=eq(FileStorageTable.c.owner_id, owner_id))


class FileStorageRepository(BaseRepository[FileStorage]):
    def get_repository_table(self) -> Table:
        return FileStorageTable

    def get_model_factory(self) -> type[FileStorage]:
        return FileStorage

    async def update_one(self, query, builder):
        raise NotImplementedError("Update is not supported for file storage")

    async def update_many(self, query, builder):
        raise NotImplementedError("Update is not supported for file storage")

    async def update_by_id(self, id, builder):
        raise NotImplementedError("Update is not supported for file storage")

    async def _update(self, query, builder):
        raise NotImplementedError("Update is not supported for file storage")
