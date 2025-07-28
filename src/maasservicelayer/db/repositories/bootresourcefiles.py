# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import join, Table

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    BootResourceFileTable,
    BootResourceSetTable,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile


class BootResourceFileClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=BootResourceFileTable.c.id.in_(ids))

    @classmethod
    def with_sha256_starting_with(cls, partial_sha256: str) -> Clause:
        return Clause(
            condition=BootResourceFileTable.c.sha256.startswith(partial_sha256)
        )

    @classmethod
    def with_sha256(cls, sha256: str) -> Clause:
        return Clause(condition=eq(BootResourceFileTable.c.sha256, sha256))

    @classmethod
    def with_sha256_in(cls, sha256_list: list[str]) -> Clause:
        return Clause(
            condition=BootResourceFileTable.c.sha256.in_(sha256_list)
        )

    @classmethod
    def with_resource_set_ids(cls, ids: list[int]) -> Clause:
        return Clause(
            condition=BootResourceFileTable.c.resource_set_id.in_(ids)
        )

    @classmethod
    def with_resource_set_id(cls, id: int) -> Clause:
        return Clause(
            condition=eq(BootResourceFileTable.c.resource_set_id, id)
        )

    @classmethod
    def with_boot_resource_ids(cls, ids: list[int]) -> Clause:
        return Clause(
            condition=BootResourceSetTable.c.resource_id.in_(ids),
            joins=[
                join(
                    BootResourceSetTable,
                    BootResourceFileTable,
                    eq(
                        BootResourceSetTable.c.id,
                        BootResourceFileTable.c.resource_set_id,
                    ),
                )
            ],
        )

    @classmethod
    def with_boot_resource_id(cls, id: int) -> Clause:
        return Clause(
            condition=eq(BootResourceSetTable.c.resource_id, id),
            joins=[
                join(
                    BootResourceSetTable,
                    BootResourceFileTable,
                    eq(
                        BootResourceSetTable.c.id,
                        BootResourceFileTable.c.resource_set_id,
                    ),
                )
            ],
        )

    @classmethod
    def with_filename(cls, filename: str) -> Clause:
        return Clause(condition=eq(BootResourceFileTable.c.filename, filename))

    @classmethod
    def with_filetype(cls, filetype: BootResourceFileType) -> Clause:
        return Clause(condition=eq(BootResourceFileTable.c.filetype, filetype))


class BootResourceFilesRepository(BaseRepository[BootResourceFile]):
    def get_repository_table(self) -> Table:
        return BootResourceFileTable

    def get_model_factory(self) -> type[BootResourceFile]:
        return BootResourceFile

    async def get_files_in_resource_set(
        self, resource_set_id: int
    ) -> list[BootResourceFile]:
        return await self.get_many(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_resource_set_id(
                    resource_set_id
                )
            )
        )
