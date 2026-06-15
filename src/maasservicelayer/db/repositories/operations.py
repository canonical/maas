# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import OperationTable, OperationTaskTable
from maasservicelayer.models.operations import Operation, OperationTask


class OperationsClauseFactory(ClauseFactory):
    @classmethod
    def with_uuid(cls, uuid: str) -> Clause:
        return Clause(condition=eq(OperationTable.c.uuid, uuid))


class OperationsRepository(BaseRepository[Operation]):
    def get_repository_table(self) -> Table:
        return OperationTable

    def get_model_factory(self) -> Type[Operation]:
        return Operation


class OperationTasksRepository(BaseRepository[OperationTask]):
    def get_repository_table(self) -> Table:
        return OperationTaskTable

    def get_model_factory(self) -> Type[OperationTask]:
        return OperationTask
