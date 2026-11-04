# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.mappers.bootresourcefiles import (
    BootResourceFileDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceFileTable
from maasservicelayer.filters.bootresourcefiles import BootResourceFileFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.bootresourcefiles import BootResourceFile


class BootResourceFilesRepository(BaseRepository[BootResourceFile]):
    def get_mapper(self) -> BootResourceFileDomainDataMapper:
        return BootResourceFileDomainDataMapper(
            BootResourceFile, BootResourceFileTable
        )

    def get_repository_table(self) -> Table:
        return BootResourceFileTable

    def get_model_factory(self) -> type[BootResourceFile]:
        return BootResourceFile

    async def get_files_in_resource_set(
        self, resource_set_id: int
    ) -> list[BootResourceFile]:
        return await self.get_many(
            query=QuerySpec(
                where=BootResourceFileFilters.with_resource_set_id(
                    resource_set_id
                )
            )
        )
