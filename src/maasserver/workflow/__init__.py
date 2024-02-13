# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from datetime import timedelta
from functools import wraps
from typing import Any, Optional
import uuid

from temporalio.service import RPCError
from twisted.internet.defer import Deferred, succeed

from maasserver.workflow.worker import get_client_async, REGION_TASK_QUEUE
from provisioningserver.utils.twisted import asynchronous, FOREVER


@asynchronous(timeout=FOREVER)
def temporal_wrapper(func):
    """
    This decorator ensures Temporal code is always executed
    with an asyncio eventloop.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            run = func(*args, **kwargs)
            if asyncio.iscoroutine(run):
                task = loop.create_task(run)
            else:
                task = loop.create_task(asyncio.ensure_future(run))
            return Deferred.fromFuture(task)
        except RuntimeError:
            ret = asyncio.run(func(*args, **kwargs))
            return succeed(ret)

    return wrapper


async def _call_workflow(
    workflow_fn: Any,
    workflow_name: str,
    workflow_id: Optional[str] = None,
    param: Optional[Any] = None,
    task_queue: Optional[str] = REGION_TASK_QUEUE,
    **kwargs,
) -> Optional[Any]:
    if not workflow_id:
        workflow_id = str(uuid.uuid4())
    if "execution_timeout" not in kwargs:
        kwargs["execution_timeout"] = timedelta(minutes=60)
    result = await workflow_fn(
        workflow_name,
        param,
        id=workflow_id,
        task_queue=task_queue,
        **kwargs,
    )
    return result


@temporal_wrapper
async def execute_workflow(
    workflow_name: str,
    workflow_id: Optional[str] = None,
    param: Optional[Any] = None,
    task_queue: Optional[str] = REGION_TASK_QUEUE,
    **kwargs,
) -> Optional[Any]:
    temporal_client = await get_client_async()
    result = await _call_workflow(
        temporal_client.execute_workflow,
        workflow_name,
        workflow_id,
        param,
        task_queue,
        **kwargs,
    )
    return result


@temporal_wrapper
async def start_workflow(
    workflow_name: str,
    workflow_id: Optional[str] = None,
    param: Optional[Any] = None,
    task_queue: Optional[str] = REGION_TASK_QUEUE,
    **kwargs,
) -> Optional[Any]:
    temporal_client = await get_client_async()
    result = await _call_workflow(
        temporal_client.start_workflow,
        workflow_name,
        workflow_id,
        param,
        task_queue,
        **kwargs,
    )
    return result


@temporal_wrapper
async def cancel_workflow(workflow_id: str) -> bool:
    temporal_client = await get_client_async()
    hdl = temporal_client.get_workflow_handle(workflow_id=workflow_id)
    try:
        await hdl.cancel()
        return True
    except RPCError:
        return False
