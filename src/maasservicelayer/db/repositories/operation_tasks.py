# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import OperationTaskTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.operations import OperationTask


class OperationTasksClauseFactory(ClauseFactory):
    @classmethod
    def with_operation_uuid(cls, operation_uuid: str) -> Clause:
        return Clause(
            condition=eq(OperationTaskTable.c.operation_uuid, operation_uuid)
        )


class OperationTasksRepository(BaseRepository[OperationTask]):
    def get_repository_table(self) -> Table:
        return OperationTaskTable

    def get_model_factory(self) -> Type[OperationTask]:
        return OperationTask

    async def list_by_operation_uuid(
        self,
        operation_uuid: str,
        page: int,
        size: int,
    ) -> ListResult[OperationTask]:
        return await self.list(
            page=page,
            size=size,
            query=QuerySpec(
                where=OperationTasksClauseFactory.with_operation_uuid(
                    operation_uuid
                )
            ),
        )
