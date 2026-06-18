# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Iterable, Type

from sqlalchemy import Table

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import OperationTable, OperationTaskTable
from maasservicelayer.models.operations import Operation, OperationTask


class OperationsClauseFactory(ClauseFactory):
    @classmethod
    def with_uuid(cls, uuid: str) -> Clause:
        return Clause(condition=eq(OperationTable.c.uuid, uuid))

    @classmethod
    def with_uuids(cls, uuids: Iterable[str]) -> Clause:
        return Clause(condition=OperationTable.c.uuid.in_(uuids))

    @classmethod
    def with_status(cls, status: OperationStatus) -> Clause:
        return Clause(condition=eq(OperationTable.c.status, status))

    @classmethod
    def with_op_type(cls, op_type: OperationType) -> Clause:
        return Clause(condition=eq(OperationTable.c.op_type, op_type))

    @classmethod
    def with_is_bulk(cls, is_bulk: bool) -> Clause:
        return Clause(condition=eq(OperationTable.c.is_bulk, is_bulk))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(OperationTable.c.user_id, user_id))


class OperationsRepository(BaseRepository[Operation]):
    def get_repository_table(self) -> Table:
        return OperationTable

    def get_model_factory(self) -> Type[Operation]:
        return Operation

    async def get_by_uuid(self, uuid: str) -> Operation | None:
        return await self.get_one(
            QuerySpec(where=Clause(eq(OperationTable.c.uuid, uuid)))
        )


class OperationTasksRepository(BaseRepository[OperationTask]):
    def get_repository_table(self) -> Table:
        return OperationTaskTable

    def get_model_factory(self) -> Type[OperationTask]:
        return OperationTask
