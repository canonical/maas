# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test executors for MAAS."""

import os
import sys
import threading
import traceback
import types

from testtools import runtest, twistedsupport
from twisted.internet import defer, interfaces, reactor
from twisted.internet.base import DelayedCall
from twisted.internet.defer import (
    Deferred,
    DeferredList,
    inlineCallbacks,
    returnValue,
)
from twisted.internet.process import reapAllProcesses
from twisted.internet.task import deferLater, LoopingCall
from twisted.internet.threads import blockingCallFromThread

__unittest = True  # skip this line from traceback in failed tests


def DelayedCall_bytes(call, __str__=DelayedCall.__str__):
    string = __str__(call)
    if isinstance(string, str):
        return string.encode("utf-8", "surrogateescape")
    else:
        return string


def DelayedCall_str(call, __str__=DelayedCall.__str__):
    string = __str__(call)
    if isinstance(string, bytes):
        return string.decode("utf-8", "surrogateescape")
    else:
        return string


# Work around https://twistedmatrix.com/trac/ticket/8306.
DelayedCall.__bytes__ = DelayedCall_bytes
DelayedCall.__str__ = DelayedCall_str

# Work around https://twistedmatrix.com/trac/ticket/8307.
DelayedCall.creator = ()

# Ask Twisted to store debug information about `DelayedCall`s.
# This greatly helps debugging Twisted errors.
DelayedCall.debug = True


class InvalidTest(Exception):
    """Signifies that the test is invalid; it's not a good test."""


def check_for_generator(result):
    if isinstance(result, types.GeneratorType):
        raise InvalidTest(
            "Test returned a generator. Should it be "
            "decorated with inlineCallbacks?"
        )
    else:
        return result


def check_for_deferred(result):
    if isinstance(result, Deferred):
        raise InvalidTest(
            "Test returned a Deferred. When the reactor is being "
            "managed by crochet the test method needs to be decorated "
            "with `crochet.wait_for`. In other cases the test class needs "
            "to define `run_tests_with` with a runner that understands "
            "Twisted, such as `MAASTwistedRunTest`."
        )
    else:
        return result


def call_belongs_to_internals(call):
    """Return True when `call` belongs to internal crochet and twisted..

    Crochet schedules a looping call that calls `reapAllProcesses` every 0.1
    seconds. This checks if this `DelayedCall` matches this signature.

    Twisted uses callLater in it's async reactor.

    :type call: :class:`DelayedCall`
    """
    if call.func.__module__ == "twisted.internet.asyncioreactor":
        return True
    elif isinstance(call.func, LoopingCall):
        return call.func.f is reapAllProcesses
    else:
        return False


class MAASRunTest(runtest.RunTest):
    """A specialisation of testtools' `RunTest`.

    It catches a common problem when writing tests for Twisted: forgetting to
    decorate a test with `inlineCallbacks` that needs it.

    Tests in `maas`, `maasserver`, and `metadataserver` run with a Twisted
    reactor managed by `crochet`. It can be easy to decorate a test that
    contains a ``yield`` with ``@wait_for`` or ``@asynchronous``, forget the
    crucial ``@inlineCallbacks``, but see that it passes... because it's not
    actually running.

    This is another reason why you should see your test fail before you make
    it pass, but why not have the computer check too?
    """

    def _run_user(self, function, *args, **kwargs):
        """Override testtools' `_run_user`.

        `_run_user` is used in testtools for running functions in the test
        case that should not normally return a generator, so we check that
        here, as it's a good sign that a test case (or `setUp`, or `tearDown`)
        is yielding without `inlineCallbacks` to support it.
        """
        try:
            result = function(*args, **kwargs)
            check_for_generator(result)
            check_for_deferred(result)
            return result
        except Exception:
            return self._got_user_exception(sys.exc_info())


class MAASCrochetReactorStalled(Exception):
    """Raised when the reactor appears to be stalled."""


class MAASCrochetDirtyThreadsError(Exception):
    """Passed to `addError` when a threadpool remains in use after a test.

    :ivar threadpools: A list of strings describing threadpools still in use.
    :ivar stacks: A list of ``(thread-description, stack)`` tuples for all
        threads running at the moment an in-use threadpool was discovered.
    """

    def __init__(self, threadpools, stacks):
        super().__init__()
        self.threadpools = threadpools
        self.stacks = stacks

    def __str__(self):
        """Return a multi-line message describing all of the unclean state."""
        msg = ["One or more threadpools were still in use:\n"]
        # Mention each non-quiet threadpool.
        for threadpool in self.threadpools:
            msg.append("  " + threadpool)
            msg.append("\n")
        # Include stacks of all threads.
        for threadDesc, stack in self.stacks:
            msg.append("\nThread %s stack:\n" % threadDesc)
            msg.extend(stack)
        return "".join(msg)


class MAASCrochetDirtyReactorError(Exception):
    """Passed to `addError` when the reactor is unclean after a test.

    :ivar delayedCalls: A list of strings desribing those delayed calls which
        weren't cleaned up.
    :ivar selectables: A list of strings describing those selectables which
        weren't cleaned up.
    """

    def __init__(self, delayedCalls, selectables):
        super().__init__()
        self.delayedCalls = delayedCalls
        self.selectables = selectables

    def __str__(self):
        """Return a multi-line message describing all of the unclean state."""
        msg = "Reactor was unclean."
        if len(self.delayedCalls) > 0:
            msg += (
                "\nDelayedCalls: (set "
                "twisted.internet.base.DelayedCall.debug = True to "
                "debug)\n"
            )
            msg += "\n".join(self.delayedCalls)
        if len(self.selectables) > 0:
            msg += "\nSelectables:\n"
            msg += "\n".join(self.selectables)
        return msg


class MAASCrochetRunTest(MAASRunTest):
    """A specialisation of `MAASRunTest`.

    In addition to `MAASRunTest`'s behaviour, this also checks that the
    Twisted reactor is clean after each test, in much the same way as
    testtools' `AsynchronousDeferredRunTest` does. This is, however, adapted
    to working with a reactor running under crochet's control.
    """

    def setUp(self):
        super().setUp()
        self.addCleanup(self._clean)

    def _clean(self):
        # Spin a bit to flush out imminent delayed calls. It's not clear why
        # we do this: left-over delayed calls are detritus like any other.
        # However, this is done by both testtools and Twisted's trial, and we
        # do it for consistency with them.
        if not self._tickReactor(0.5):
            raise MAASCrochetReactorStalled(
                "Reactor did not respond after 500ms."
            )
        # Ensure that all threadpools are quiet. Do this first because we must
        # crash the whole run if they don't go quiet before the next test.
        dirtyPools, threadStacks = blockingCallFromThread(
            reactor, self._cleanThreads
        )
        if len(dirtyPools) != 0:
            raise MAASCrochetDirtyThreadsError(dirtyPools, threadStacks)
        # Find leftover delayed calls and selectables in use.
        dirtyCalls, dirtySelectables = blockingCallFromThread(
            reactor, self._cleanReactor
        )
        if len(dirtyCalls) != 0 or len(dirtySelectables) != 0:
            raise MAASCrochetDirtyReactorError(dirtyCalls, dirtySelectables)

    def _tickReactor(self, timeout):
        ticked = threading.Event()
        reactor.callFromThread(ticked.set)
        return ticked.wait(timeout)

    def _cleanReactor(self):
        """Return leftover delayed calls, selectables, and threadpools."""
        return (
            [str(leftover) for leftover in self._cleanPending()],
            [repr(leftover) for leftover in self._cleanSelectables()],
        )

    def _cleanPending(self):
        """Cancel all pending calls and return their string representations.

        Delayed calls belonging to crochet and twisted internals are ignored.
        """
        for call in reactor.getDelayedCalls():
            if call.active() and not call_belongs_to_internals(call):
                yield call
                call.cancel()

    def _cleanSelectables(self):
        """Remove all selectables and return their string representation.

        Kill any of them that were processes.
        """
        for sel in reactor.removeAll():
            if interfaces.IProcessTransport.providedBy(sel):
                sel.signalProcess("KILL")
            yield sel

    def _cleanThreads(self):
        """Find threadpools still in use and wait for them to quiesce."""
        noisy = [
            pool
            for pool in self._getThreadpools()
            if not self._isThreadpoolQuiet(pool)
        ]

        if len(noisy) == 0:
            stacks = None  # Save the effort.
        else:
            stacks = self._captureThreadStacks()

        d = DeferredList(
            map(self._waitForThreadpoolToQuiesce, noisy),
            fireOnOneErrback=True,
            consumeErrors=True,
        )

        def unwrap(results):
            return [repr(pool) for _, pool in results], stacks

        return d.addCallback(unwrap)

    def _getThreadpools(self):
        """Get currently configured threadpools."""
        for poolName in {"threadpool", "threadpoolForDatabase"}:
            pool = getattr(reactor, poolName, None)
            if pool is not None:
                yield pool

    @inlineCallbacks
    def _waitForThreadpoolToQuiesce(self, pool):
        """Return a :class:`Deferred` that waits for `pool` to quiesce."""
        now = reactor.seconds()
        until = now + 90.0
        while now < until:
            if self._isThreadpoolQuiet(pool):
                # The pool is quiet. It's safe to move on. Return the pool so
                # that it can still be reported.
                returnValue(pool)
            else:
                # Pause for a second to give it a chance to go quiet.
                now = yield deferLater(reactor, 1.0, reactor.seconds)
        else:
            # Despite waiting a long time the pool will not go quiet. The
            # validity of subsequent tests is compromised. Die immediately.
            print("ThreadPool", repr(pool), "is NOT quiet.", file=sys.stderr)
            os._exit(3)

    def _isThreadpoolQuiet(self, pool):
        """Is the given threadpool quiet, i.e. not in use?

        This can handle MAAS's custom threadpools as well as Twisted's default
        implementation.
        """
        lock = getattr(pool, "lock", None)
        if isinstance(lock, defer.DeferredLock):
            return not lock.locked
        elif isinstance(lock, defer.DeferredSemaphore):
            return lock.tokens == lock.limit
        else:
            return len(pool.working) == 0

    def _captureThreadStacks(self):
        """Capture the stacks for all currently running threads.

        :return: A list of ``(thread-description, stack)`` tuples. See
            `traceback.format_stack` for the format of ``stack``.
        """
        threads = {t.ident: t for t in threading.enumerate()}

        def describe(ident):
            if ident in threads:
                return repr(threads[ident])
            else:
                return "<*Unknown* %d>" % ident

        return [
            (describe(ident), traceback.format_stack(frame))
            for ident, frame in sys._current_frames().items()
        ]


class MAASTwistedRunTest(twistedsupport.AsynchronousDeferredRunTest):
    """A specialisation of testtools' `AsynchronousDeferredRunTest`.

    It catches a common problem when writing tests for Twisted: forgetting to
    decorate a test with `inlineCallbacks` that needs it.

    Tests in `maas`, `maasserver`, and `metadataserver` run with a Twisted
    reactor managed by `crochet`, so don't use this; it will result in a
    deadlock.
    """

    def _run_user(self, function, *args):
        """Override testtools' `_run_user`.

        `_run_user` is used in testtools for running functions in the test
        case that may or may not return a `Deferred`. Here we also check for
        generators, a good sign that a test case (or `setUp`, or `tearDown`)
        is yielding without `inlineCallbacks` to support it.
        """
        d = defer.maybeDeferred(function, *args)
        d.addCallback(check_for_generator)
        d.addErrback(self._got_user_failure)
        return d
