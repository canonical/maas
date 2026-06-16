# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import timedelta
from functools import wraps

import structlog
from temporalio import workflow
from temporalio.common import SearchAttributeKey
from temporalio.exceptions import ApplicationError, is_cancelled_exception

from maascommon.enums.operations import OperationStatus
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

logger = structlog.getLogger()

UPDATE_OPERATION_STATUS_TIMEOUT = timedelta(seconds=30)
UPDATE_CURRENT_TASK_TIMEOUT = timedelta(seconds=30)

# Activities names
UPDATE_OPERATION_STATUS_ACTIVITY_NAME = "update-operation-status"
UPDATE_CURRENT_TASK_ACTIVITY_NAME = "update-current-task"

OPERATION_UUID_SEARCH_ATTRIBUTE = SearchAttributeKey.for_keyword(
    "OperationUUID"
)


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
            await services.operation_tasks.start_task(
                operation_uuid=param.operation_uuid,
                name=param.name,
                task_number=param.task_number,
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
            f" but the search attribute {OPERATION_UUID_SEARCH_ATTRIBUTE}"
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
