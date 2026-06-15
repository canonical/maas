# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.operations import OperationStatus, OperationTaskStatus
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
from maasservicelayer.models.operations import Operation, OperationTask
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow


class OperationsService(
    BaseService[Operation, OperationsRepository, OperationBuilder]
):
    def __init__(
        self,
        context: Context,
        operations_repository: OperationsRepository,
    ):
        super().__init__(context, operations_repository)

    async def update_status(
        self,
        operation_uuid: str,
        status: OperationStatus,
        result: dict | None = None,
        error: str | None = None,
    ) -> Operation:
        builder = OperationBuilder(status=status)
        if status == OperationStatus.RUNNING:
            builder.started = utcnow()
        elif status in (
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
        ):
            builder.finished = utcnow()
        # On success the operation is no longer running any task; on failure we
        # leave current_task untouched so the user can see where it stopped.
        if status == OperationStatus.COMPLETED:
            builder.current_task = ""
        if result is not None:
            builder.result_errors = result
        elif error is not None:
            builder.result_errors = {"error": error}

        return await self.update_one(
            query=QuerySpec(
                where=OperationsClauseFactory.with_uuid(operation_uuid)
            ),
            builder=builder,
        )

    async def set_current_task(
        self, operation_uuid: str, name: str
    ) -> Operation:
        return await self.update_one(
            query=QuerySpec(
                where=OperationsClauseFactory.with_uuid(operation_uuid)
            ),
            builder=OperationBuilder(current_task=name),
        )


class OperationTasksService(
    BaseService[OperationTask, OperationTasksRepository, OperationTaskBuilder]
):
    def __init__(
        self,
        context: Context,
        operation_tasks_repository: OperationTasksRepository,
        operations_service: OperationsService,
    ):
        super().__init__(context, operation_tasks_repository)
        self.operations_service = operations_service

    async def start_task(
        self, operation_uuid: str, name: str, task_number: int
    ) -> OperationTask:
        task = await self.create(
            builder=OperationTaskBuilder(
                operation_uuid=operation_uuid,
                name=name,
                task_number=task_number,
                status=OperationTaskStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await self.operations_service.set_current_task(operation_uuid, name)
        return task
