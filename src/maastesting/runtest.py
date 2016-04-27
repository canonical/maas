# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test executors for MAAS."""

__all__ = [
    'MAASCrochetRunTest',
    'MAASRunTest',
    'MAASTwistedRunTest',
    ]

import sys
import threading
import types

from testtools import (
    deferredruntest,
    runtest,
)
from twisted.internet import (
    defer,
    interfaces,
    reactor,
)
from twisted.internet.base import DelayedCall
from twisted.internet.process import reapAllProcesses
from twisted.internet.task import LoopingCall
from twisted.internet.threads import blockingCallFromThread


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
            "decorated with inlineCallbacks?")
    else:
        return result


def call_belongs_to_crochet(call):
    """Return True when `call` belongs to crochet.

    Crochet schedules a looping call that calls `reapAllProcesses` every 0.1
    seconds. This checks if this `DelayedCall` matches this signature.

    :type call: :class:`DelayedCall`
    """
    if isinstance(call.func, LoopingCall):
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
            return check_for_generator(result)
        except:
            return self._got_user_exception(sys.exc_info())


class MAASCrochetReactorStalled(Exception):
    """Raised when the reactor appears to be stalled."""


class MAASCrochetDirtyReactorError(Exception):
    """Passed to `addError` when the reactor is unclean after a test.

    :ivar delayedCalls: A list of strings desribing those delayed calls which
        weren't cleaned up.
    :ivar selectables: A list of strings describing those selectables which
        weren't cleaned up.
    :ivar threadpools: A list of strings describing those threadpools still in
        use.
    """

    def __init__(self, delayedCalls, selectables, threadpools):
        super(MAASCrochetDirtyReactorError, self).__init__()
        self.delayedCalls = delayedCalls
        self.selectables = selectables
        self.threadpools = threadpools

    def __str__(self):
        """Return a multi-line message describing all of the unclean state."""
        msg = "Reactor was unclean."
        if len(self.delayedCalls) > 0:
            msg += ("\nDelayedCalls: (set "
                    "twisted.internet.base.DelayedCall.debug = True to "
                    "debug)\n")
            msg += "\n".join(self.delayedCalls)
        if len(self.selectables) > 0:
            msg += "\nSelectables:\n"
            msg += "\n".join(self.selectables)
        if len(self.threadpools) > 0:
            msg += "\nThreadpools:\n"
            msg += "\n".join(self.threadpools)
        return msg


class MAASCrochetRunTest(MAASRunTest):
    """A specialisation of `MAASRunTest`.

    In addition to `MAASRunTest`'s behaviour, this also checks that the
    Twisted reactor is clean after each test, in much the same way as
    testtools' `AsynchronousDeferredRunTest` does. This is, however, adapted
    to working with a reactor running under crochet's control.
    """

    def _run_core(self):
        """Override testtools' `_run_core`.

        Check that the reactor is clean and that no delayed calls are still
        laying around. This is different from `AsynchronousDeferredRunTest`
        that does more advanced things with the reactor. This just simply
        checks if its clean.
        """
        super(MAASCrochetRunTest, self)._run_core()
        try:
            self._clean()
        except:
            self._got_user_exception(sys.exc_info())

    def _clean(self):
        # Spin a bit to flush out imminent delayed calls.
        if not self._tickReactor(0.5):
            raise MAASCrochetReactorStalled(
                "Reactor did not respond after 500ms.")
        # Find leftover delayed calls, selectables, and threadpools in use.
        dirty = blockingCallFromThread(reactor, self._cleanReactor)
        if any(len(items) > 0 for items in dirty):
            raise MAASCrochetDirtyReactorError(*dirty)

    def _tickReactor(self, timeout):
        ticked = threading.Event()
        reactor.callFromThread(ticked.set)
        return ticked.wait(timeout)

    def _cleanReactor(self):
        """Return leftover delayed calls, selectables, and threadpools."""
        return (
            [str(leftover) for leftover in self._cleanPending()],
            [repr(leftover) for leftover in self._cleanSelectables()],
            [repr(leftover) for leftover in self._cleanThreads()],
        )

    def _cleanPending(self):
        """Cancel all pending calls and return their string representations.

        Delayed calls belonging to crochet are ignored.
        """
        for call in reactor.getDelayedCalls():
            if call.active() and not call_belongs_to_crochet(call):
                yield call
                call.cancel()

    def _cleanSelectables(self):
        """Remove all selectables and return their string representation.

        Kill any of them that were processes.
        """
        for sel in reactor.removeAll():
            if interfaces.IProcessTransport.providedBy(sel):
                sel.signalProcess('KILL')
            yield sel

    def _cleanThreads(self):
        for poolName in "threadpool", "threadpoolForDatabase":
            try:
                pool = getattr(reactor, poolName)
            except AttributeError:
                pass  # Pool not configured.
            else:
                lock = getattr(pool, "lock", None)
                if isinstance(lock, defer.DeferredLock):
                    if lock.locked:
                        yield pool
                elif isinstance(lock, defer.DeferredSemaphore):
                    if lock.tokens != lock.limit:
                        yield pool
                else:
                    if len(pool.working) != 0:
                        yield pool


class MAASTwistedRunTest(deferredruntest.AsynchronousDeferredRunTest):
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
