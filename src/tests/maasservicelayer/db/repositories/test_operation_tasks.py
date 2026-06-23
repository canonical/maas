# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.operation_tasks import (
    OperationTasksClauseFactory,
    OperationTasksRepository,
)
from maasservicelayer.models.operations import OperationTask
from tests.fixtures.factories.operations import (
    create_test_operation_entry,
    create_test_operation_task_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestOperationTasksClauseFactory:
    def test_with_operation_uuid(self) -> None:
        clause = OperationTasksClauseFactory.with_operation_uuid("op-uuid")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation_task.operation_uuid = 'op-uuid'"
        )


class TestOperationTasksRepository(RepositoryCommonTests[OperationTask]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> OperationTasksRepository:
        return OperationTasksRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[OperationTask]:
        operation = await create_test_operation_entry(fixture)
        return [
            await create_test_operation_task_entry(
                fixture,
                operation_uuid=operation.uuid,
                task_number=i,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> OperationTask:
        operation = await create_test_operation_entry(fixture)
        return await create_test_operation_task_entry(
            fixture, operation_uuid=operation.uuid
        )

    async def test_list_by_operation_uuid(
        self,
        repository_instance: OperationTasksRepository,
        fixture: Fixture,
    ) -> None:
        operation = await create_test_operation_entry(fixture, uuid="list-op")
        await create_test_operation_task_entry(
            fixture, operation_uuid=operation.uuid, task_number=0
        )
        await create_test_operation_task_entry(
            fixture, operation_uuid=operation.uuid, task_number=1
        )
        result = await repository_instance.list_by_operation_uuid(
            operation_uuid=operation.uuid, page=1, size=10
        )
        assert result.total == 2

    async def test_list_by_operation_uuid_filters_by_uuid(
        self,
        repository_instance: OperationTasksRepository,
        fixture: Fixture,
    ) -> None:
        op_a = await create_test_operation_entry(fixture, uuid="op-a")
        op_b = await create_test_operation_entry(fixture, uuid="op-b")
        await create_test_operation_task_entry(
            fixture, operation_uuid=op_a.uuid, task_number=0
        )
        await create_test_operation_task_entry(
            fixture, operation_uuid=op_b.uuid, task_number=0
        )
        result = await repository_instance.list_by_operation_uuid(
            operation_uuid=op_a.uuid, page=1, size=10
        )
        assert result.total == 1
        assert result.items[0].operation_uuid == op_a.uuid
