# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import timedelta
from functools import wraps

import structlog
from temporalio import workflow
from temporalio.exceptions import ApplicationError

from maascommon.enums.operations import OperationStatus
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

logger = structlog.getLogger()

OPERATION_UUID_SEARCH_ATTRIBUTE = "OperationUUID"

UPDATE_OPERATION_STATUS_TIMEOUT = timedelta(seconds=30)

# Activities names
UPDATE_OPERATION_STATUS_ACTIVITY_NAME = "update-operation-status"


# Activities parameters
@dataclass
class UpdateOperationStatusParam:
    operation_uuid: str
    status: OperationStatus
    result: dict | None = None
    error: str | None = None


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


def track_operation_status(func):
    """Decorate a workflow run method to track its operation status in the DB."""

    @wraps(func)
    async def wrapper(self, param):
        info = workflow.info()
        operation_uuid = info.search_attributes.get(
            OPERATION_UUID_SEARCH_ATTRIBUTE
        )
        if not operation_uuid:
            raise ApplicationError(
                f"Status tracking is enabled for workflow {info.workflow_type}"
                f" but the search attribute {OPERATION_UUID_SEARCH_ATTRIBUTE}"
                " has not been set."
            )
        # Search attributes are always returned as a list.
        operation_uuid = str(operation_uuid[0])

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
            await workflow.execute_local_activity(
                UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
                UpdateOperationStatusParam(
                    operation_uuid=operation_uuid,
                    status=OperationStatus.FAILED,
                    error=str(e),
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
