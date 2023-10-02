import asyncio
from functools import wraps

from twisted.internet.defer import Deferred, succeed

from maasserver.eventloop import services
from maasserver.workflow.worker import get_client_async
from provisioningserver.utils.twisted import asynchronous

TEMPORAL_SIGNAL_TIMEOUT = 10


def run_in_temporal_eventloop(fn, *args, **kwargs):
    temporal_worker = services.getServiceNamed("temporal-worker")
    return temporal_worker.loop.create_task(
        asyncio.ensure_future(fn(*args, **kwargs))
    )


@asynchronous(timeout=TEMPORAL_SIGNAL_TIMEOUT)
def temporal_signal(func):
    """
    This decorator ensures Temporal signals are always executed
    with an asyncio eventloop.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        async def _send_signal(*args, **kwargs):
            temporal_client = await get_client_async()
            kwargs["temporal_client"] = temporal_client
            await asyncio.ensure_future(func(*args, **kwargs))

        try:
            loop = asyncio.get_event_loop()
            task = loop.create_task(_send_signal(*args, **kwargs))
            return Deferred.fromFuture(task)
        except RuntimeError:
            try:
                task = run_in_temporal_eventloop(_send_signal, *args, **kwargs)
                return Deferred.fromFuture(task)
            except KeyError:  # in worker proc
                asyncio.run(_send_signal(*args, **kwargs))
                return succeed()

    return wrapper
