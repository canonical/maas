import asyncio
from functools import cache
import logging
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker
from twisted.internet.defer import Deferred, DeferredLock, inlineCallbacks

from maasserver.config import RegionConfiguration
from provisioningserver.utils.env import MAAS_UUID
from provisioningserver.utils.twisted import asynchronous

logger = logging.getLogger(__name__)

# TODO Globals?
_temporal_client: Optional[Client] = None
_temporal_client_lock = DeferredLock()
_temporal_worker_event = asyncio.Event()


@cache
def task_queue_name():
    """Returns task queue name for the region"""
    return f"maas-region-{MAAS_UUID.get()}"


@asynchronous
@inlineCallbacks
def get_temporal_client(force=False):
    """
    Returns connected Temporal client
    """
    global _temporal_client

    yield _temporal_client_lock.acquire()
    if not _temporal_client or force:
        logger.info("Initializing _temporal_client global")
        with RegionConfiguration.open() as config:
            _temporal_client = yield Deferred.fromFuture(
                asyncio.ensure_future(
                    Client.connect(
                        config.temporal_server,
                        namespace=config.temporal_namespace,
                    )
                )
            )
    yield _temporal_client_lock.release()
    return _temporal_client


@asynchronous
@inlineCallbacks
def start_temporal_worker(*args, **kwargs):
    """Initializes and starts Temporal's `Worker`"""
    global _temporal_worker_event
    client: Client = yield get_temporal_client()

    # Provide default task queue name if empty
    if "task_queue" not in kwargs:
        kwargs["task_queue"] = task_queue_name()

    async def run_worker():
        worker = Worker(client, *args, **kwargs)
        logger.info("Worker starting")
        async with worker:
            _temporal_worker_event.clear()
            await _temporal_worker_event.wait()
            _temporal_worker_event.clear()
            logger.info("Worker stopped")

    asyncio.create_task(run_worker())


@asynchronous
@inlineCallbacks
def stop_temporal_worker():
    """Issues a stop signal to the worker"""
    global _temporal_worker_event
    logger.info("Worker stopping (event set)")
    _temporal_worker_event.set()


@asynchronous
@inlineCallbacks
def start_workflow(*args, **kwargs):
    """A convenience wrapper around `client.start_workflow`"""
    client: Client = yield get_temporal_client()

    # Provide default task queue name if empty
    if "task_queue" not in kwargs:
        kwargs["task_queue"] = task_queue_name()

    logger.info(
        f"Starting workflow with the parameters: \n\targs: {args}\n\tkwargs: {kwargs}"
    )
    yield Deferred.fromFuture(
        asyncio.ensure_future(client.start_workflow(*args, **kwargs))
    )


@asynchronous
@inlineCallbacks
def execute_workflow(*args, **kwargs):
    """A convenience wrapper around `client.execute_workflow`"""
    client: Client = yield get_temporal_client()

    # Provide default task queue name if empty
    if "task_queue" not in kwargs:
        kwargs["task_queue"] = task_queue_name()

    logger.info(
        f"Executing workflow with the parameters: \n\targs: {args}\n\tkwargs: {kwargs}"
    )
    yield Deferred.fromFuture(
        asyncio.ensure_future(client.execute_workflow(*args, **kwargs))
    )
