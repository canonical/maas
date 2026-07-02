# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps

import structlog
from temporalio import workflow
from temporalio.client import WorkflowExecutionStatus
from temporalio.common import (
    SearchAttributeKey,
    SearchAttributePair,
    TypedSearchAttributes,
    WorkflowIDReusePolicy,
)
from temporalio.exceptions import (
    ApplicationError,
    is_cancelled_exception,
    WorkflowAlreadyStartedError,
)
from temporalio.service import RPCError, RPCStatusCode

from maascommon.enums.operations import OperationStatus, OperationType
from maascommon.workflows.operation import (
    BULK_OPERATION_WORKFLOW_NAME,
    RECONCILE_OPERATIONS_WORKFLOW_NAME,
    workflow_name_for_operation_type,
)
from maasservicelayer.utils.date import utcnow
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

logger = structlog.getLogger()

UPDATE_OPERATION_STATUS_TIMEOUT = timedelta(seconds=30)
UPDATE_CURRENT_TASK_TIMEOUT = timedelta(seconds=30)
RECONCILE_STUCK_ACCEPTED_TIMEOUT = timedelta(seconds=60)
RECONCILE_IN_PROGRESS_TIMEOUT = timedelta(seconds=60)
ROLLUP_BULK_STATUS_TIMEOUT = timedelta(seconds=30)
CREATE_CHILD_OPERATION_TIMEOUT = timedelta(seconds=30)

STUCK_OPERATION_GRACE_PERIOD = timedelta(minutes=5)

UPDATE_OPERATION_STATUS_ACTIVITY_NAME = "update-operation-status"
UPDATE_CURRENT_TASK_ACTIVITY_NAME = "update-current-task"
RECONCILE_STUCK_ACCEPTED_ACTIVITY_NAME = "reconcile-stuck-accepted-operations"
RECONCILE_IN_PROGRESS_ACTIVITY_NAME = "reconcile-in-progress-operations"
ROLLUP_BULK_STATUS_ACTIVITY_NAME = "rollup-bulk-operation-status"
CREATE_CHILD_OPERATION_ACTIVITY_NAME = "create-child-operation"

OPERATION_UUID_SEARCH_ATTRIBUTE = SearchAttributeKey.for_keyword(
    "OperationUUID"
)

TEMPORAL_STATUS_TO_OPERATION_STATUS = {
    WorkflowExecutionStatus.COMPLETED: OperationStatus.COMPLETED,
    WorkflowExecutionStatus.FAILED: OperationStatus.FAILED,
    WorkflowExecutionStatus.CANCELED: OperationStatus.CANCELLED,
    WorkflowExecutionStatus.TERMINATED: OperationStatus.CANCELLED,
}


# Activities parameters
@dataclass
class UpdateOperationStatusParam:
    operation_uuid: str
    status: OperationStatus
    result: dict | None = None
    error: str | None = None


@dataclass
class UpdateCurrentTaskParam:
    operation_uuid: str
    name: str
    task_number: int


@dataclass
class CreateChildOperationParam:
    op_type: OperationType
    parent_uuid: str
    resource_id: int | None = None
    resource_type: str | None = None
    parameters: dict | None = None


class OperationActivity(ActivityBase):
    @activity_defn_with_context(name=UPDATE_OPERATION_STATUS_ACTIVITY_NAME)
    async def update_operation_status(
        self, param: UpdateOperationStatusParam
    ) -> None:
        async with self.start_transaction() as services:
            await services.operations.update_status(
                operation_uuid=param.operation_uuid,
                status=param.status,
                result=param.result,
                error=param.error,
            )

    @activity_defn_with_context(name=UPDATE_CURRENT_TASK_ACTIVITY_NAME)
    async def update_current_task(self, param: UpdateCurrentTaskParam) -> None:
        async with self.start_transaction() as services:
            await services.operations.start_task(
                operation_uuid=param.operation_uuid,
                name=param.name,
                task_number=param.task_number,
            )

    @activity_defn_with_context(name=RECONCILE_STUCK_ACCEPTED_ACTIVITY_NAME)
    async def reconcile_stuck_accepted_operations(self) -> None:
        cutoff = utcnow() - STUCK_OPERATION_GRACE_PERIOD
        async with self.start_transaction() as services:
            operations = (
                await services.operations.list_stuck_accepted_operations(
                    created_before=cutoff
                )
            )
        for operation in operations:
            workflow_name = workflow_name_for_operation_type(operation.op_type)
            if workflow_name is None:
                raise ApplicationError(
                    f"No workflow is mapped to operation type "
                    f"'{operation.op_type}'.",
                    non_retryable=True,
                )
            try:
                await self.temporal_client.start_workflow(
                    workflow_name,
                    operation.parameters,
                    id=operation.uuid,
                    task_queue=REGION_TASK_QUEUE,
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                    search_attributes=TypedSearchAttributes(
                        [
                            SearchAttributePair(
                                OPERATION_UUID_SEARCH_ATTRIBUTE, operation.uuid
                            )
                        ]
                    ),
                )
            except WorkflowAlreadyStartedError:
                logger.debug(
                    "Operation workflow already exists; skipping reconciliation",
                    operation_uuid=operation.uuid,
                )

    @activity_defn_with_context(name=RECONCILE_IN_PROGRESS_ACTIVITY_NAME)
    async def reconcile_in_progress_operations(self) -> None:
        async with self.start_transaction() as services:
            operations = (
                await services.operations.list_in_progress_operations()
            )
            for operation in operations:
                handle = self.temporal_client.get_workflow_handle(
                    operation.uuid
                )
                try:
                    description = await handle.describe()
                except RPCError as e:
                    if e.status == RPCStatusCode.NOT_FOUND:
                        if operation.status == OperationStatus.CANCELLING:
                            status = OperationStatus.CANCELLED
                            error = None
                        else:
                            status = OperationStatus.FAILED
                            error = "Workflow execution not found in Temporal."
                        await services.operations.update_status(
                            operation_uuid=operation.uuid,
                            status=status,
                            error=error,
                        )
                        continue
                    raise
                status = TEMPORAL_STATUS_TO_OPERATION_STATUS.get(
                    description.status  # pyright: ignore[reportArgumentType]
                )
                if status is None:
                    continue
                await services.operations.update_status(
                    operation_uuid=operation.uuid,
                    status=status,
                )

    @activity_defn_with_context(name=CREATE_CHILD_OPERATION_ACTIVITY_NAME)
    async def create_child_operation(
        self, param: CreateChildOperationParam
    ) -> str:
        async with self.start_transaction() as services:
            return await services.operations.create_child_operation_row(
                op_type=param.op_type,
                parent_uuid=param.parent_uuid,
                resource_id=param.resource_id,
                resource_type=param.resource_type,
                parameters=param.parameters,
            )

    @activity_defn_with_context(name=ROLLUP_BULK_STATUS_ACTIVITY_NAME)
    async def rollup_bulk_operation_status(self, parent_uuid: str) -> None:
        async with self.start_transaction() as services:
            await services.operations.update_bulk_status_from_children(
                parent_uuid
            )


def _get_operation_uuid() -> str:
    """Return the operation UUID tracked by the running workflow.

    The UUID is read from the ``OperationUUID`` search attribute set when the
    workflow is started. Raises if the attribute is missing.
    """
    info = workflow.info()
    operation_uuid = info.typed_search_attributes.get(
        OPERATION_UUID_SEARCH_ATTRIBUTE
    )
    if not operation_uuid:
        raise ApplicationError(
            f"Operation tracking is enabled for workflow {info.workflow_type}"
            f" but the search attribute {OPERATION_UUID_SEARCH_ATTRIBUTE.name}"
            " has not been set."
        )
    return operation_uuid


async def update_current_task(name: str, task_number: int) -> None:
    """Record the task a tracked workflow is about to start.

    Call this from a tracked workflow run method before starting each task. It
    persists ``name`` as the operation's current task and creates the matching
    operation task row.
    """
    await workflow.execute_local_activity(
        UPDATE_CURRENT_TASK_ACTIVITY_NAME,
        UpdateCurrentTaskParam(
            operation_uuid=_get_operation_uuid(),
            name=name,
            task_number=task_number,
        ),
        start_to_close_timeout=UPDATE_CURRENT_TASK_TIMEOUT,
    )


def track_operation_status(func):
    """Decorate a workflow run method to track its operation status in the DB."""

    @wraps(func)
    async def wrapper(self, param):
        operation_uuid = _get_operation_uuid()

        try:
            await workflow.execute_local_activity(
                UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
                UpdateOperationStatusParam(
                    operation_uuid=operation_uuid,
                    status=OperationStatus.RUNNING,
                ),
                start_to_close_timeout=UPDATE_OPERATION_STATUS_TIMEOUT,
            )

            result = await func(self, param)

            await workflow.execute_local_activity(
                UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
                UpdateOperationStatusParam(
                    operation_uuid=operation_uuid,
                    status=OperationStatus.COMPLETED,
                    result=result,
                ),
                start_to_close_timeout=UPDATE_OPERATION_STATUS_TIMEOUT,
            )
            return result
        except Exception as e:
            logger.error(
                "Workflow failed",
                operation_uuid=operation_uuid,
                error=str(e),
            )
            if is_cancelled_exception(e):
                status = OperationStatus.CANCELLED
                error = f"Operation {operation_uuid} was cancelled."
            else:
                status = OperationStatus.FAILED
                error = str(e)
            await workflow.execute_local_activity(
                UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
                UpdateOperationStatusParam(
                    operation_uuid=operation_uuid,
                    status=status,
                    error=error,
                ),
                start_to_close_timeout=UPDATE_OPERATION_STATUS_TIMEOUT,
            )
            raise

    return wrapper


def workflow_run_with_tracked_operation(func):
    """
    You MUST use this decorator instead of @workflow_run_with_context
    on operation-tracked workflows.
    """
    return workflow_run_with_context(track_operation_status(func))


@workflow.defn(name=RECONCILE_OPERATIONS_WORKFLOW_NAME, sandboxed=False)
class ReconcileOperationsWorkflow:
    """Reconcile operations whose state has drifted from Temporal."""

    @workflow_run_with_context
    async def run(self) -> None:
        await workflow.execute_activity(
            RECONCILE_STUCK_ACCEPTED_ACTIVITY_NAME,
            start_to_close_timeout=RECONCILE_STUCK_ACCEPTED_TIMEOUT,
        )
        await workflow.execute_activity(
            RECONCILE_IN_PROGRESS_ACTIVITY_NAME,
            start_to_close_timeout=RECONCILE_IN_PROGRESS_TIMEOUT,
        )


@workflow.defn(name=BULK_OPERATION_WORKFLOW_NAME, sandboxed=False)
class BulkOperationWorkflow:
    """Wait for child operations to finish and roll up the bulk parent status."""

    @workflow_run_with_context
    async def run(self, param: dict) -> None:
        parent_uuid = _get_operation_uuid()
        await workflow.execute_local_activity(
            UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
            UpdateOperationStatusParam(
                operation_uuid=parent_uuid,
                status=OperationStatus.RUNNING,
            ),
            start_to_close_timeout=UPDATE_OPERATION_STATUS_TIMEOUT,
        )
        handles = []
        for child in param["children"]:
            child_uuid = await workflow.execute_activity(
                CREATE_CHILD_OPERATION_ACTIVITY_NAME,
                CreateChildOperationParam(
                    op_type=OperationType(child["op_type"]),
                    parent_uuid=parent_uuid,
                    resource_id=child.get("resource_id"),
                    resource_type=child.get("resource_type"),
                    parameters=child.get("parameters"),
                ),
                start_to_close_timeout=CREATE_CHILD_OPERATION_TIMEOUT,
            )
            child_workflow_name = workflow_name_for_operation_type(
                OperationType(child["op_type"])
            )
            if child_workflow_name is None:
                raise ApplicationError(
                    f"No workflow is mapped to operation type"
                    f" '{child['op_type']}'.",
                    non_retryable=True,
                )
            handle = await workflow.start_child_workflow(
                child_workflow_name,
                child.get("parameters"),
                id=child_uuid,
                search_attributes=TypedSearchAttributes(
                    [
                        SearchAttributePair(
                            OPERATION_UUID_SEARCH_ATTRIBUTE, child_uuid
                        )
                    ]
                ),
            )
            handles.append(handle)
        await asyncio.gather(*handles, return_exceptions=True)
        await workflow.execute_activity(
            ROLLUP_BULK_STATUS_ACTIVITY_NAME,
            parent_uuid,
            start_to_close_timeout=ROLLUP_BULK_STATUS_TIMEOUT,
        )
