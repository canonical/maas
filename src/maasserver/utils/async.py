# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with asynchronous operations."""

__all__ = [
    'DeferredHooks',
    "gather",
]

from collections import deque
from contextlib import contextmanager
from itertools import count
from queue import Queue
import threading

from maasserver.exceptions import IteratorReusedError
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    LONGTIME,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    maybeDeferred,
)
from twisted.python import log


class UseOnceIterator:
    """An iterator that is usable only once."""

    def __init__(self, *args):
        """Create a new :class:`UseOnceIterator`.

        Takes the same arguments as iter().
        """
        self.iterable = iter(*args)
        self.has_run_once = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.has_run_once:
            raise IteratorReusedError(
                "It is not possible to reuse a UseOnceIterator.")
        try:
            return next(self.iterable)
        except StopIteration:
            self.has_run_once = True
            raise


@asynchronous(timeout=FOREVER)
def gather(calls, timeout=10.0):
    """gather(calls, timeout=10.0)

    Issue calls into the reactor, passing results back to another thread.

    Note that `gather` does not explicitly report to the caller that it
    has timed-out; calls are silently cancelled and the generator simply
    reaches its end. If this information is important to your code, put
    in place some mechanism to check that all expected responses have
    been received, or create a modified version of thus function with
    the required behaviour.

    :param calls: An iterable of no-argument callables to be called in
        the reactor thread. Each will be called via
        :py:func:`~twisted.internet.defer.maybeDeferred`.

    :param timeout: The number of seconds before further results are
        ignored. Outstanding results will be cancelled.

    :return: A :class:`UseOnceIterator` of results. A result might be a
        failure, i.e. an instance of
        :py:class:`twisted.python.failure.Failure`, or a valid result;
        it's up to the caller to check.

    """

    # Prepare of a list of Deferreds that we're going to wait for.
    deferreds = [maybeDeferred(call) for call in calls]

    # We'll use this queue (thread-safe) to pass results back.
    queue = Queue()

    # A sentinel to mark the end of the results.
    done = object()

    # This function will get called if not all results are in before
    # `timeout` seconds have passed. It puts `done` into the queue to
    # indicate the end of results, and cancels all outstanding deferred
    # calls.
    def cancel():
        queue.put(done)
        for deferred in deferreds:
            try:
                deferred.cancel()
            except:
                log.err()

    if timeout is None:
        canceller = None
    else:
        canceller = reactor.callLater(timeout, cancel)

    countdown = count(len(deferreds), -1)

    # Callback to report the result back to the queue. If it's the last
    # result to be reported, `done` is put into the queue, and the
    # delayed call to `cancel` is itself cancelled.
    def report(result):
        queue.put(result)
        if next(countdown) == 1:
            queue.put(done)
            if canceller is not None:
                if canceller.active():
                    canceller.cancel()

    for deferred in deferreds:
        deferred.addBoth(report)

    # If there are no calls then there will be no results, so we put
    # `done` into the queue, and cancel the nascent delayed call to
    # `cancel`, if it exists.
    if len(deferreds) == 0:
        queue.put(done)
        if canceller is not None:
            canceller.cancel()

    # Return an iterator to the invoking thread that will stop at the
    # first sign of the `done` sentinel.
    return UseOnceIterator(queue.get, done)


def suppress(failure, *exceptions):
    """Used as a errback, suppress the given exceptions."""
    failure.trap(*exceptions)


class DeferredHooks(threading.local):
    """A utility class for managing hooks that are specified as Deferreds.

    This is meant to be used by non-Twisted code to register hooks that need
    to be run at some later time *in Twisted*. This is a common pattern in
    MAAS, where the web-application needs to arrange post-commit actions that
    mutate remote state, via RPC for example.
    """

    def __init__(self):
        super(DeferredHooks, self).__init__()
        self.hooks = deque()

    @synchronous
    def add(self, d):
        assert isinstance(d, Deferred)
        self.hooks.append(d)

    @contextmanager
    def savepoint(self):
        """Context manager that saves the current hooks on the way in.

        If the context exits with an exception the newly added hooks are
        cancelled, and the saved hooks are restored.

        If the context exits cleanly, the saved hooks are restored, and the
        newly hooks are added to the end of the hook queue.
        """
        saved = self.hooks
        self.hooks = deque()
        try:
            yield
        except:
            self.reset()
            raise
        else:
            saved.extend(self.hooks)
        finally:
            self.hooks = saved

    @synchronous
    def fire(self):
        """Fire all hooks in sequence, in the reactor.

        If a hook fails, the subsequent hooks will be cancelled (by calling
        ``.cancel()``), and the exception will propagate out of this method.
        """
        try:
            while len(self.hooks) > 0:
                hook = self.hooks.popleft()
                self._fire_in_reactor(hook).wait(LONGTIME)
        finally:
            # Ensure that any remaining hooks are cancelled.
            self.reset()

    @synchronous
    def reset(self):
        """Cancel all hooks in sequence, in the reactor.

        This calls each hook's ``.cancel()`` method. If any of these raise an
        exception, it will be logged; it will not prevent cancellation of
        other hooks.
        """
        try:
            while len(self.hooks) > 0:
                hook = self.hooks.popleft()
                self._cancel_in_reactor(hook).wait(LONGTIME)
        finally:
            # Belt-n-braces.
            self.hooks.clear()

    @staticmethod
    @asynchronous
    def _fire_in_reactor(hook):
        hook.callback(None)
        return hook

    @staticmethod
    @asynchronous
    def _cancel_in_reactor(hook):
        hook.addErrback(suppress, CancelledError)
        hook.addErrback(log.err)
        try:
            hook.cancel()
        except:
            # The canceller has failed. We take a hint from DeferredList here,
            # by logging the exception and moving on.
            log.err(_why="Failure when cancelling hook.")
        else:
            return hook
