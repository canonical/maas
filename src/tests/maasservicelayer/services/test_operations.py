# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.operations import (
    OperationStatus,
    OperationTaskStatus,
    OperationType,
)
from maasservicelayer.builders.operations import (
    OperationBuilder,
    OperationTaskBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
    OperationTasksRepository,
)
from maasservicelayer.models.base import MaasBaseModel, ResourceBuilder
from maasservicelayer.models.operations import Operation, OperationTask
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.operations import (
    OperationsService,
    OperationTasksService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

ERROR_MESSAGE = "operation failed"

TEST_OPERATION = Operation(
    id=1,
    uuid="op-uuid",
    op_type=OperationType.MACHINE_DEPLOY,
    status=OperationStatus.ACCEPTED,
    is_bulk=False,
    created=utcnow(),
    updated=utcnow(),
)

TEST_OPERATION_TASK = OperationTask(
    id=1,
    operation_uuid="op-uuid",
    name="task1",
    task_number=1,
    status=OperationTaskStatus.RUNNING,
)


@pytest.mark.asyncio
class TestCommonOperationsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return OperationsService(
            context=Context(),
            operations_repository=Mock(OperationsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_OPERATION

    @pytest.fixture
    def builder_model(self) -> type[ResourceBuilder]:
        return OperationBuilder


@pytest.mark.asyncio
class TestOperationsService:
    def _service(self, repository: Mock) -> OperationsService:
        return OperationsService(
            context=Context(),
            operations_repository=repository,
        )

    async def test_update_status_running_sets_started(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.RUNNING}
        )
        service = self._service(repository)

        await service.update_status("op-uuid", OperationStatus.RUNNING)

        query = repository.get_one.call_args.kwargs["query"]
        assert query == QuerySpec(
            where=OperationsClauseFactory.with_uuid("op-uuid")
        )
        builder = repository.update_by_id.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["status"] == OperationStatus.RUNNING
        assert "started" in populated
        assert "finished" not in populated
        assert "result_errors" not in populated

    async def test_update_status_completed_stores_result(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.COMPLETED}
        )
        service = self._service(repository)

        await service.update_status(
            "op-uuid",
            OperationStatus.COMPLETED,
            result={"deployed": True},
        )

        builder = repository.update_by_id.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["status"] == OperationStatus.COMPLETED
        assert "finished" in populated
        assert populated["result_errors"] == {"deployed": True}
        assert populated["current_task"] == ""
        assert "started" not in populated

    async def test_update_status_failed_stores_error(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.FAILED}
        )
        service = self._service(repository)

        await service.update_status(
            "op-uuid", OperationStatus.FAILED, error=ERROR_MESSAGE
        )

        builder = repository.update_by_id.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["status"] == OperationStatus.FAILED
        assert "finished" in populated
        assert "started" not in populated
        assert populated["result_errors"] == {"error": ERROR_MESSAGE}
        # On failure current_task is left untouched so the user can see where
        # the operation stopped.
        assert "current_task" not in populated

    async def test_set_current_task(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION
        service = self._service(repository)

        await service.set_current_task("op-uuid", "task1")

        query = repository.get_one.call_args.kwargs["query"]
        assert query == QuerySpec(
            where=OperationsClauseFactory.with_uuid("op-uuid")
        )
        builder = repository.update_by_id.call_args.kwargs["builder"]
        assert builder.populated_fields()["current_task"] == "task1"


@pytest.mark.asyncio
class TestCommonOperationTasksService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return OperationTasksService(
            context=Context(),
            operation_tasks_repository=Mock(OperationTasksRepository),
            operations_service=Mock(OperationsService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_OPERATION_TASK

    @pytest.fixture
    def builder_model(self) -> type[ResourceBuilder]:
        return OperationTaskBuilder


@pytest.mark.asyncio
class TestOperationTasksService:
    async def test_start_task(self) -> None:
        repository = Mock(OperationTasksRepository)
        repository.create.return_value = TEST_OPERATION_TASK
        operations_service = Mock(OperationsService)
        service = OperationTasksService(
            context=Context(),
            operation_tasks_repository=repository,
            operations_service=operations_service,
        )

        await service.start_task("op-uuid", "task1", 1)

        builder = repository.create.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["operation_uuid"] == "op-uuid"
        assert populated["name"] == "task1"
        assert populated["task_number"] == 1
        assert populated["status"] == OperationTaskStatus.RUNNING
        assert "started_at" in populated
        operations_service.set_current_task.assert_awaited_once_with(
            "op-uuid", "task1"
        )
