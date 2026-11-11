# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.mappers.operations import OperationsDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import OperationTable, OperationTaskTable
from maasservicelayer.filters.operations import OperationsFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.operations import Operation, OperationTask


class OperationsRepository(BaseRepository[Operation]):
    def get_mapper(self) -> OperationsDomainDataMapper:
        return OperationsDomainDataMapper(Operation, OperationTable)

    def get_repository_table(self) -> Table:
        return OperationTable

    def get_model_factory(self) -> Type[Operation]:
        return Operation

    async def get_by_uuid(self, uuid: str) -> Operation | None:
        return await self.get_one(
            QuerySpec(where=OperationsFilters.with_uuid(uuid))
        )


class OperationTasksRepository(BaseRepository[OperationTask]):
    def get_repository_table(self) -> Table:
        return OperationTaskTable

    def get_model_factory(self) -> Type[OperationTask]:
        return OperationTask
