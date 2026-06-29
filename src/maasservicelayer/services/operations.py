# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from uuid import uuid4

from temporalio.common import (
    SearchAttributeKey,
    SearchAttributePair,
    TypedSearchAttributes,
)

from maascommon.enums.operations import (
    OperationStatus,
    OperationTaskStatus,
    OperationType,
)
from maascommon.workflows.operation import (
    OPERATION_UUID_SEARCH_ATTRIBUTE,
    workflow_name_for_operation_type,
)
from maasservicelayer.builders.operations import (
    OperationBuilder,
    OperationTaskBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operation_tasks import (
    OperationTasksRepository,
)
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    CONFLICT_VIOLATION_TYPE,
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.operations import Operation, OperationTask
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow


class OperationsService(
    BaseService[Operation, OperationsRepository, OperationBuilder]
):
    def __init__(
        self,
        context: Context,
        operations_repository: OperationsRepository,
        operation_tasks_repository: OperationTasksRepository,
        temporal_service: TemporalService,
    ):
        super().__init__(context, operations_repository)
        self.operation_tasks_repository = operation_tasks_repository
        self.temporal_service = temporal_service

    async def start_task(
        self, operation_uuid: str, name: str, task_number: int
    ) -> OperationTask:
        task = await self.operation_tasks_repository.create(
            builder=OperationTaskBuilder(
                operation_uuid=operation_uuid,
                name=name,
                task_number=task_number,
                status=OperationTaskStatus.RUNNING,
                started_at=utcnow(),
            )
        )
        await self.set_current_task(operation_uuid, name)
        return task

    async def create_accepted_operation(
        self,
        op_type: OperationType,
        resource_id: int | None = None,
        resource_type: str | None = None,
        parameters: dict | None = None,
        user_id: int | None = None,
    ) -> Operation:
        """Create an ACCEPTED operation and schedule its workflow after commit."""
        workflow_name = workflow_name_for_operation_type(op_type)
        if workflow_name is None:
            raise ValueError(
                f"No workflow is mapped to operation type '{op_type}'."
            )
        operation = await self.create(
            builder=OperationBuilder(
                uuid=str(uuid4()),
                op_type=op_type,
                status=OperationStatus.ACCEPTED,
                resource_id=resource_id,
                resource_type=resource_type,
                parameters=parameters,
                user_id=user_id,
                is_bulk=False,
            )
        )
        self.temporal_service.register_workflow_call(
            workflow_name=workflow_name,
            parameter=parameters,
            workflow_id=operation.uuid,
            wait=False,
            search_attributes=TypedSearchAttributes(
                [
                    SearchAttributePair(
                        SearchAttributeKey.for_keyword(
                            OPERATION_UUID_SEARCH_ATTRIBUTE
                        ),
                        operation.uuid,
                    )
                ]
            ),
        )
        return operation

    async def list_stuck_accepted_operations(
        self, created_before: datetime
    ) -> list[Operation]:
        """Return ACCEPTED operations created before ``created_before``."""
        return await self.repository.get_many(
            query=QuerySpec(
                where=OperationsClauseFactory.and_clauses(
                    [
                        OperationsClauseFactory.with_status(
                            OperationStatus.ACCEPTED
                        ),
                        OperationsClauseFactory.created_before(created_before),
                    ]
                )
            )
        )

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
            builder.current_task = None
        if result is not None:
            builder.result = result
        elif error is not None:
            builder.result = {"error": error}

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

    async def list_for_user(
        self,
        page: int,
        size: int,
        user_id: int,
        can_view_all: bool,
        query: QuerySpec | None = None,
    ) -> ListResult[Operation]:
        if can_view_all:
            return await self.repository.list(
                page=page, size=size, query=query
            )
        user_clause = OperationsClauseFactory.with_user_id(user_id)
        if query and query.where:
            combined = OperationsClauseFactory.and_clauses(
                [query.where, user_clause]
            )
            filtered_query = QuerySpec(where=combined)
        else:
            filtered_query = QuerySpec(where=user_clause)
        return await self.repository.list(
            page=page, size=size, query=filtered_query
        )

    async def get_by_uuid_for_user(
        self,
        uuid: str,
        user_id: int,
        can_view_all: bool,
    ) -> Operation:
        operation = await self.repository.get_by_uuid(uuid)
        if operation is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Operation with uuid '{uuid}' was not found.",
                    )
                ]
            )
        if can_view_all:
            return operation
        if operation.user_id != user_id:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Operation with uuid '{uuid}' was not found.",
                    )
                ]
            )
        return operation

    async def cancel_for_user(
        self,
        uuid: str,
        user_id: int,
        can_edit_all: bool,
        can_view_all: bool,
    ) -> Operation:
        operation = await self.get_by_uuid_for_user(
            uuid, user_id=user_id, can_view_all=can_view_all
        )
        if not can_edit_all and operation.user_id != user_id:
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                        message=f"User is not permitted to cancel operation with uuid '{uuid}'.",
                    )
                ]
            )
        if operation.status in (
            OperationStatus.CANCELLING,
            OperationStatus.CANCELLED,
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
        ):
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=CONFLICT_VIOLATION_TYPE,
                        message=f"Operation '{uuid}' cannot be cancelled because it is in the {operation.status} status.",
                    )
                ]
            )
        return await self.update_status(
            operation_uuid=uuid,
            status=OperationStatus.CANCELLING,
        )

    async def list_tasks_for_operation(
        self,
        operation_uuid: str,
        page: int,
        size: int,
    ) -> ListResult[OperationTask]:
        return await self.operation_tasks_repository.list_by_operation_uuid(
            operation_uuid=operation_uuid,
            page=page,
            size=size,
        )
