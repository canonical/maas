# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with asynchronous operations."""

from collections import deque
from contextlib import contextmanager
from itertools import count
from queue import Queue
import threading

from twisted.internet import reactor
from twisted.internet.defer import CancelledError, Deferred, maybeDeferred

from maasserver.exceptions import IteratorReusedError
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    LONGTIME,
    suppress,
    synchronous,
)

log = LegacyLogger()


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
                "It is not possible to reuse a UseOnceIterator."
            )
        try:
            return next(self.iterable)
        except StopIteration:
            self.has_run_once = True
            raise


@asynchronous(timeout=FOREVER)
def gather(calls, timeout=10.0):
    """Deprecated version of `gatherCallResults()`.

    This method yields only the result of each call, rather than a (call,
    result) tuple. Thus, callers can only match up the original call with the
    result by calling `gatherCallResults()`.
    """
    for call, result in gatherCallResults(calls, timeout=timeout):  # noqa: B007
        yield result


@asynchronous(timeout=FOREVER)
def gatherCallResults(calls, timeout=10.0):
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

    # Prepare of a list of Deferreds that we're going to wait for. The original
    # input call objects need to be preserved, since the caller may need to
    # match the results up with the original call.
    calls = list(calls)

    # This list must be in the same order as the list of `calls`.
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
            except Exception:
                log.err(None, "Failure gathering results.")

    if timeout is None:
        canceller = None
    else:
        canceller = reactor.callLater(timeout, cancel)

    countdown = count(len(calls), -1)

    def finished():
        queue.put(done)
        if canceller is not None:
            if canceller.active():
                canceller.cancel()

    # Callback to report the result back to the queue. If it's the last
    # result to be reported, `done` is put into the queue, and the
    # delayed call to `cancel` is itself cancelled.
    def report(result, call):
        queue.put((call, result))
        if next(countdown) == 1:
            finished()

    # We need to add callbacks to the `deferred` here, but the caller needs
    # a reference to the original call.
    for index, deferred in enumerate(deferreds):
        deferred.addBoth(report, calls[index])

    # If there are no calls then there will be no results, so we put
    # `done` into the queue, and cancel the nascent delayed call to
    # `cancel`, if it exists.
    if len(calls) == 0:
        finished()

    # Return an iterator to the invoking thread that will stop at the
    # first sign of the `done` sentinel.
    return UseOnceIterator(queue.get, done)


class DeferredHooks(threading.local):
    """A utility class for managing hooks that are specified as Deferreds.

    This is meant to be used by non-Twisted code to register hooks that need
    to be run at some later time *in Twisted*. This is a common pattern in
    MAAS, where the web-application needs to arrange post-commit actions that
    mutate remote state, via RPC for example.
    """

    def __init__(self):
        super().__init__()
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
        except Exception:
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
        hook.addErrback(log.err, "Failure when cancelling hook.")
        try:
            hook.cancel()
        except Exception:
            # The canceller has failed. We take a hint from DeferredList here,
            # by logging the exception and moving on.
            log.err(None, "Failure when cancelling hook.")
        else:
            return hook
