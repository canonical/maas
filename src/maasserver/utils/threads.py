# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Stuff relating to threads in the MAAS Region Controller.

Threads in Python aren't great, but they're okay for what we need. However,
Django's ORM closely weds database connections to threads, so we use specific
pools to limit the number of connections each `regiond` process will consume.

"""

__all__ = [
    "callOutToDatabase",
    "deferToDatabase",
    "install_database_pool",
    "install_database_unpool",
    "install_default_pool",
    "make_database_pool",
    "make_default_pool",
]

from django.conf import settings
from twisted.internet import reactor, threads
from twisted.internet.defer import DeferredSemaphore

from maasserver.utils.orm import (
    count_queries,
    ExclusivelyConnected,
    FullyConnected,
    TotallyDisconnected,
)
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    ThreadPool,
    ThreadUnpool,
)

log = LegacyLogger()


max_threads_for_default_pool = 50

# Maximum number of database connections this worker can use. 9 connections is
# allowed as 1 is reserved for the `PostgresListener`. Allowing each worker to
# have a maximum of 10 connections open at a time. A region controller with
# 4 workers will use a maximum of 40 connections. This allows 2 region
# controllers to run without needing to increase the maximum number of
# PostgreSQL connection (default is 100 connections).
max_threads_for_database_pool = 9


def make_default_pool(maxthreads=max_threads_for_default_pool):
    """Create a general thread-pool for non-database activity.

    Its sole consumer is the old-school web application, i.e. the plain HTTP
    service. All threads are fully connected to the database.
    """
    return ThreadPool(0, maxthreads, "default", TotallyDisconnected)


def make_database_pool(maxthreads=max_threads_for_database_pool):
    """Create a general thread-pool for database activity.

    Its consumer are the old-school web application, i.e. the plain HTTP and
    HTTP API services, and the WebSocket service, for the responsive web UI.
    All threads are fully connected to the database.
    """
    return ThreadPool(0, maxthreads, "database", FullyConnected)


def make_database_unpool(maxthreads=max_threads_for_database_pool):
    """Create a general non-thread-pool for database activity.

    Its consumer are the old-school web application, i.e. the plain HTTP and
    HTTP API services, and the WebSocket service, for the responsive web UI.
    Each thread is fully connected to the database.

    However, this is a :class:`ThreadUnpool`, which means that threads are not
    actually pooled: a new thread is created for each task. This is ideal for
    testing, to improve isolation between tests.
    """
    return ThreadUnpool(DeferredSemaphore(maxthreads), ExclusivelyConnected)


@asynchronous(timeout=FOREVER)
def install_default_pool(maxthreads=max_threads_for_default_pool):
    """Install a custom pool as Twisted's global/reactor thread-pool.

    Disallow all database activity in the reactor thread-pool. Why such a
    strict policy? We've been following Django's model, where threads and
    database connections are wedded together. In MAAS this limits concurrency,
    contributes to crashes and deadlocks, and has spawned workarounds like
    post-commit hooks. From here on, using a database connection requires the
    use of a specific, separate, carefully-sized, thread-pool.
    """
    if reactor.threadpool is None:
        # Start with ZERO threads to avoid pulling in all of Django's
        # configuration straight away; it may not be ready yet.
        reactor.threadpool = make_default_pool(maxthreads)
        reactor.callWhenRunning(reactor.threadpool.start)
        reactor.addSystemEventTrigger(
            "during", "shutdown", reactor.threadpool.stop
        )
    else:
        raise AssertionError(
            "Too late; global/reactor thread-pool has "
            "already been configured and installed."
        )


@asynchronous(timeout=FOREVER)
def install_database_pool(maxthreads=max_threads_for_database_pool):
    """Install a pool for database activity."""
    if getattr(reactor, "threadpoolForDatabase", None) is None:
        # Start with ZERO threads to avoid pulling in all of Django's
        # configuration straight away; it may not be ready yet.
        reactor.threadpoolForDatabase = make_database_pool(maxthreads)
        reactor.callInDatabase = reactor.threadpoolForDatabase.callInThread
        reactor.callWhenRunning(reactor.threadpoolForDatabase.start)
        reactor.addSystemEventTrigger(
            "during", "shutdown", reactor.threadpoolForDatabase.stop
        )
    else:
        raise AssertionError(
            "Too late; database thread-pool has already "
            "been configured and installed."
        )


@asynchronous(timeout=FOREVER)
def install_database_unpool(maxthreads=max_threads_for_database_pool):
    """Install a pool for database activity particularly suited to testing.

    See `make_database_unpool` for details.
    """
    try:
        reactor.threadpoolForDatabase  # noqa: B018
    except AttributeError:
        reactor.threadpoolForDatabase = make_database_unpool(maxthreads)
        reactor.callInDatabase = reactor.threadpoolForDatabase.callInThread
        reactor.callWhenRunning(reactor.threadpoolForDatabase.start)
        reactor.addSystemEventTrigger(
            "during", "shutdown", reactor.threadpoolForDatabase.stop
        )
    else:
        raise AssertionError(
            "Too late; database thread-pool has already "
            "been configured and installed."
        )


def deferToDatabase(func, *args, **kwargs):
    """Call `func` in a thread where database activity is permitted."""
    if settings.DEBUG and getattr(settings, "DEBUG_QUERIES", False):
        func = count_queries(log.debug)(func)
    return threads.deferToThreadPool(
        reactor, reactor.threadpoolForDatabase, func, *args, **kwargs
    )


def callOutToDatabase(thing, func, *args, **kwargs):
    """Call out to the given `func` in a database thread, but return `thing`.

    This is identical to `callOutToThread` except that it uses the database
    thread-pool.
    """
    return deferToDatabase(func, *args, **kwargs).addCallback(lambda _: thing)
