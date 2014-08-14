# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to the Twisted/Crochet execution environment."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'asynchronous',
    'deferred',
    'deferWithTimeout',
    'pause',
    'reactor_sync',
    'retries',
    'synchronous',
    ]

from contextlib import contextmanager
from functools import wraps
import sys
import threading

from crochet import run_in_reactor
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    maybeDeferred,
    )
from twisted.python import threadable
from twisted.python.threadable import isInIOThread


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)
    return wrapper


def asynchronous(func):
    """Decorates a function to ensure that it always runs in the reactor.

    If the wrapper is called from the reactor thread, it will call
    straight through to the wrapped function. It will not be wrapped by
    `maybeDeferred` for example.

    If the wrapper is called from another thread, it will return a
    :class:`crochet.EventualResult`, as if it had been decorated with
    `crochet.run_in_reactor`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    func_in_reactor = run_in_reactor(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        if isInIOThread():
            return func(*args, **kwargs)
        else:
            return func_in_reactor(*args, **kwargs)
    return wrapper


def synchronous(func):
    """Decorator to ensure that `func` never runs in the reactor thread.

    If the wrapped function is called from the reactor thread, this will
    raise a :class:`AssertionError`, implying that this is a programming
    error. Calls from outside the reactor will proceed unaffected.

    There is an asymmetry with the `asynchronous` decorator. The reason
    is that it is essential to be aware when `deferToThread()` is being
    used, so that in-reactor code knows to synchronise with it, to add a
    callback to the :class:`Deferred` that it returns, for example. The
    expectation with `asynchronous` is that the return value is always
    important, and will be appropriate to the environment in which it is
    utilised.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as synchronous, or blocking.

    :raises AssertionError: When called inside the reactor thread.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # isInIOThread() can return True if the reactor has previously been
        # started but has now stopped, so don't test isInIOThread() until
        # we've also checked if the reactor is running.
        if reactor.running and isInIOThread():
            raise AssertionError(
                "Function %s(...) must not be called in the "
                "reactor thread." % func.__name__)
        else:
            return func(*args, **kwargs)
    return wrapper


@contextmanager
def reactor_sync():
    """Context manager that synchronises with the reactor thread.

    When holding this context the reactor thread is suspended, and the current
    thread is marked as the IO thread. You can then do almost any work that
    you would normally do in the reactor thread.

    The "almost" above refers to things that track state by thread, which with
    Twisted is not much. However, things like :py:mod:`twisted.python.context`
    may not behave quite as you expect.
    """
    # If we're already running in the reactor thread this is a no-op; we're
    # already synchronised with the execution of the reactor.
    if isInIOThread():
        yield
        return

    # If we're not running in the reactor thread, we need to synchronise
    # execution, being careful to avoid deadlocks.
    sync = threading.Condition()
    reactorThread = threadable.ioThread

    # When calling sync.wait() we specify a timeout of sys.maxint. The default
    # timeout of None cannot be interrupted by SIGINT, aka Ctrl-C, which can
    # be more than a little frustrating.

    def sync_io():
        # This runs in the reactor's thread. It first gets a lock on `sync`.
        with sync:
            # This then notifies a single waiter. That waiter will be the
            # thread that this context-manager was invoked from.
            sync.notify()
            # This then waits to be notified back. During this time the
            # reactor cannot run.
            sync.wait(sys.maxint)

    # Grab a lock on the `sync` condition.
    with sync:
        # Schedule `sync_io` to be called in the reactor. We do this with the
        # lock held so that `sync_io` cannot progress quite yet.
        reactor.callFromThread(sync_io)
        # Now, wait. This allows `sync_io` obtain the lock on `sync`, and then
        # awaken me via `notify()`. When `wait()` returns we once again have a
        # lock on `sync`. We're able to get this lock because `sync_io` goes
        # into `sync.wait()`, thus releasing its lock on it.
        sync.wait(sys.maxint)
        try:
            # Mark the current thread as the IO thread. This makes the
            # `asynchronous` and `synchronous` decorators DTRT.
            threadable.ioThread = threadable.getThreadID()
            # Allow this thread to execute while holding `sync`. The reactor
            # is prevented from spinning because `sync_io` is in `wait()`.
            yield
        finally:
            # Restore the IO thread.
            threadable.ioThread = reactorThread
            # Wake up `sync_io`, which can then run to completion, though not
            # until we release our lock `sync` by exiting this context.
            sync.notify()


def retries(timeout=30, interval=1, clock=reactor):
    """Helper for retrying something, sleeping between attempts.

    Yields ``(elapsed, remaining, wait)`` tuples, giving times in
    seconds. The last item, `wait`, is the suggested amount of time to
    sleep before trying again.

    @param timeout: From now, how long to keep iterating, in seconds.
    @param interval: The sleep between each iteration, in seconds.
    @param clock: An optional `IReactorTime` provider. Defaults to the
        installed reactor.

    """
    start = clock.seconds()
    end = start + timeout
    while True:
        now = clock.seconds()
        if now < end:
            wait = min(interval, end - now)
            yield now - start, end - now, wait
        else:
            break


def pause(duration, clock=reactor):
    """Pause execution for `duration` seconds.

    Returns a `Deferred` that will fire after `duration` seconds.
    """
    d = Deferred(lambda d: dc.cancel())
    dc = clock.callLater(duration, d.callback, None)
    return d


def deferWithTimeout(timeout, func=None, *args, **kwargs):
    """Call `func`, returning a `Deferred`.

    The `Deferred` will be cancelled after `timeout` seconds if not otherwise
    called.

    If `func` is not specified, or None, this will return a new
    :py:class:`Deferred` instance that will be cancelled after `timeout`
    seconds. Do not specify `args` or `kwargs` if `func` is `None`.

    :param timeout: The number of seconds before cancelling `d`.
    :param func: A callable, or `None`.
    :param args: Positional arguments to pass to `func`.
    :param kwargs: Keyword arguments to pass to `func`.
    """
    if func is None and len(args) == len(kwargs) == 0:
        d = Deferred()
    else:
        d = maybeDeferred(func, *args, **kwargs)

    timeoutCall = reactor.callLater(timeout, d.cancel)

    def done(result):
        if timeoutCall.active():
            timeoutCall.cancel()
        return result

    return d.addBoth(done)
