# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from datetime import timedelta
from functools import wraps
import random

import structlog
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError, TemporalError

from maascommon.enums.operations import OperationStatus
from maascommon.tracing import get_or_set_trace_id
from maascommon.workflows.operation import (
    OPERATION_UUID_SEARCH_ATTRIBUTE,
    UPDATE_OPERATION_STATUS_ACTIVITY_NAME,
    UpdateOperationStatusParam,
)
from maasservicelayer.context import Context

logger = structlog.getLogger()

UPDATE_OPERATION_STATUS_TIMEOUT = timedelta(seconds=30)


def activity_defn_with_context(name):
    """
    You MUST always use this decorator instead of the plain @activity.defn.
    """

    def decorator(func):
        @activity.defn(name=name)
        @wraps(func)
        async def wrapper(*args, **kwargs):
            context = Context(trace_id=get_or_set_trace_id())
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(trace_id=context.trace_id)
            logger.info(f"Starting activity {func.__name__}")
            res = await func(*args, **kwargs)
            logger.info(
                "Activity has completed",
                elapsed_time_seconds=context.get_elapsed_time_seconds(),
            )
            return res

        return wrapper

    return decorator


def workflow_run_with_context(func):
    """
    You MUST always use this decorator instead of the plain @workflow.run.
    """

    @workflow.run
    @wraps(func)
    async def wrapper(*args, **kwargs):
        context = Context(trace_id=get_or_set_trace_id())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=context.trace_id)
        logger.info(f"Starting workflow {func.__qualname__}")
        res = await func(*args, **kwargs)
        logger.info(
            "Workflow has completed",
            elapsed_time_seconds=context.get_elapsed_time_seconds(),
        )
        return res

    return wrapper


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


def async_retry(retries=5, backoff_ms=1000):
    def wrapper(fn):
        @wraps(fn)
        async def wrapped(*args, **kwargs):
            tries = 0
            while True:
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    tries += 1
                    if tries == retries:
                        raise e
                    else:
                        sleep_ms = backoff_ms * (2**tries) + random.uniform(
                            0, 1
                        )
                        await asyncio.sleep(sleep_ms / 1000)

        return wrapped

    return wrapper


def get_error_message_from_temporal_exc(e: TemporalError) -> str:
    """Extract the original error message from Temporal error.

    Navigates through the chain of causes to find the first ApplicationError,
    which contains the original error message.
    """
    cause = e.cause
    while cause:
        if isinstance(cause, ApplicationError):
            return str(cause)
        # Check if this cause has its own cause
        cause = getattr(cause, "cause", None)
    return str(cause) if cause else str(e)
