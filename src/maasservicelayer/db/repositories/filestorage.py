#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode
from operator import eq
from typing import List

from sqlalchemy import delete, Table, update
from sqlalchemy.dialects.postgresql import insert

from maasservicelayer.builders.filestorage import FileStorageBuilder
from maasservicelayer.db.mappers.base import BaseDomainDataMapper
from maasservicelayer.db.mappers.filestorage import FileStorageDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import FileStorageTable
from maasservicelayer.filters.filestorage import FileStorageFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.filestorage import FileStorage


class FileStorageRepository(BaseRepository[FileStorage]):
    def get_repository_table(self) -> Table:
        return FileStorageTable

    def get_model_factory(self) -> type[FileStorage]:
        return FileStorage

    def get_mapper(self) -> BaseDomainDataMapper:
        return FileStorageDomainDataMapper(
            FileStorage, self.get_repository_table()
        )

    async def create(self, builder):
        raise NotImplementedError(
            "Create is not supported for file storage. Use `create_or_update`."
        )

    async def create_many(self, builders):
        raise NotImplementedError(
            "Create is not supported for file storage. Use `create_or_update`."
        )

    async def create_or_update(
        self, builder: FileStorageBuilder
    ) -> FileStorage:
        resource = self.mapper.build_resource(builder)

        # We get_one instead of using on_conflict_do_update because the uniqueness
        # constraint is based on (filename, key). A new key is set when creating
        # the builder in the handler, so we issue a get for just the filename to
        # check if we need to overwrite any existing file.
        existing_file = await self.get_one(
            query=QuerySpec(
                where=FileStorageFilters.and_filters(
                    [
                        FileStorageFilters.with_filename(resource["filename"]),
                        FileStorageFilters.with_owner_id(resource["owner_id"]),
                    ]
                )
            )
        )

        if not existing_file:
            stmt = (
                insert(self.get_repository_table())
                .returning(self.get_repository_table())
                .values(**resource.get_values())
            )
        else:
            stmt = (
                update(self.get_repository_table())
                .where(eq(FileStorageTable.c.id, existing_file.id))
                .returning(self.get_repository_table())
                .values(dict(content=resource["content"]))
            )

        result = (await self.execute_stmt(stmt)).one()
        result_dict = result._asdict()
        result_dict["content"] = b64decode(result_dict["content"])
        return self.get_model_factory()(**result_dict)

    async def _get(self, query: QuerySpec) -> List[FileStorage]:
        """
        This override is required to convert the string-based, base64-encoded
        file content that the database uses, to a valid `bytes` representation
        used by the service layer model.

        This is called by `get_one`, `get_by_id`, and `get_many`.
        """
        stmt = self.select_all_statement()
        stmt = self._translate(query).enrich_stmt(stmt)

        result = (await self.execute_stmt(stmt)).all()
        stored_files = []
        for row in result:
            row_dict = row._asdict()
            row_dict["content"] = b64decode(row_dict["content"])
            stored_files.append(self.get_model_factory()(**row_dict))
        return stored_files

    async def _delete(self, query: QuerySpec) -> List[FileStorage]:
        stmt = delete(FileStorageTable).returning(FileStorageTable)
        stmt = self._translate(query).enrich_stmt(stmt)
        result = (await self.execute_stmt(stmt)).all()
        stored_files = []
        for row in result:
            row_dict = row._asdict()
            row_dict["content"] = b64decode(row_dict["content"])
            stored_files.append(self.get_model_factory()(**row_dict))
        return stored_files

    async def list(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[FileStorage]:
        result = await super().list(page, size, query)
        for file in result.items:
            file.content = b64decode(file.content)
        return result

    async def list_all(
        self, query: QuerySpec | None = None
    ) -> List[FileStorage]:
        files = await super().list_all(query)
        for file in files:
            file.content = b64decode(file.content)
        return files

    async def update_one(self, query, builder):
        raise NotImplementedError("Update is not supported for file storage")

    async def update_many(self, query, builder):
        raise NotImplementedError("Update is not supported for file storage")

    async def update_by_id(self, id, builder):
        raise NotImplementedError("Update is not supported for file storage")

    async def _update(self, query, builder):
        raise NotImplementedError("Update is not supported for file storage")
