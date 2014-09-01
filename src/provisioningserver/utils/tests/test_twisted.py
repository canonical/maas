# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Twisted/Crochet-related utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import operator
from random import (
    randint,
    random,
    )
import re
import time

from crochet import EventualResult
from maastesting.matchers import (
    IsCallable,
    MockCalledOnceWith,
    )
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
    )
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver.utils import twisted as twisted_module
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferWithTimeout,
    FOREVER,
    pause,
    reactor_sync,
    retries,
    synchronous,
    )
from testtools.deferredruntest import extract_result
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesException,
    MatchesListwise,
    MatchesStructure,
    Not,
    Raises,
    )
from testtools.testcase import ExpectedException
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    inlineCallbacks,
    )
from twisted.internet.task import Clock
from twisted.internet.threads import deferToThread
from twisted.python import threadable
from twisted.python.failure import Failure


def return_args(*args, **kwargs):
    return args, kwargs


class TestAsynchronousDecorator(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_in_reactor_thread(self):
        result = asynchronous(return_args)(1, 2, three=3)
        self.assertEqual(((1, 2), {"three": 3}), result)

    @inlineCallbacks
    def test_in_other_thread(self):
        def do_stuff_in_thread():
            result = asynchronous(return_args)(3, 4, five=5)
            self.assertThat(result, IsInstance(EventualResult))
            return result.wait()
        # Call do_stuff_in_thread() from another thread.
        result = yield deferToThread(do_stuff_in_thread)
        # do_stuff_in_thread() waited for the result of return_args().
        # The arguments passed back match those passed in from
        # do_stuff_in_thread().
        self.assertEqual(((3, 4), {"five": 5}), result)


noop = lambda: None


class TestAsynchronousDecoratorWithTimeout(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_timeout_cannot_be_None(self):
        self.assertRaises(ValueError, asynchronous, noop, timeout=None)

    def test_timeout_cannot_be_negative(self):
        self.assertRaises(ValueError, asynchronous, noop, timeout=-1)

    def test_timeout_can_be_int(self):
        self.assertThat(asynchronous(noop, timeout=1), IsCallable())

    def test_timeout_can_be_long(self):
        self.assertThat(asynchronous(noop, timeout=1L), IsCallable())

    def test_timeout_can_be_float(self):
        self.assertThat(asynchronous(noop, timeout=1.0), IsCallable())

    def test_timeout_can_be_forever(self):
        self.assertThat(asynchronous(noop, timeout=FOREVER), IsCallable())


class TestAsynchronousDecoratorWithTimeoutDefined(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("finite", {"timeout": random()}),
        ("forever", {"timeout": FOREVER}),
    )

    def test_in_reactor_thread(self):
        return_args_async = asynchronous(return_args, self.timeout)
        result = return_args_async(1, 2, three=3)
        self.assertEqual(((1, 2), {"three": 3}), result)

    @inlineCallbacks
    def test_in_other_thread(self):
        return_args_async = asynchronous(return_args, self.timeout)
        # Call self.return_args from another thread.
        result = yield deferToThread(return_args_async, 3, 4, five=5)
        # The arguments passed back match those passed in.
        self.assertEqual(((3, 4), {"five": 5}), result)

    @inlineCallbacks
    def test__passes_timeout_to_wait(self):
        # These mocks are going to help us tell a story of a timeout.
        run_in_reactor = self.patch(twisted_module, "run_in_reactor")
        func_in_reactor = run_in_reactor.return_value
        eventual_result = func_in_reactor.return_value
        wait = eventual_result.wait
        wait.return_value = sentinel.result

        # Our placeholder function, and its wrapped version.
        do_nothing = lambda: None
        do_nothing_async = asynchronous(do_nothing, timeout=self.timeout)

        # Call our wrapped function in a thread so that the wrapper calls back
        # into the IO thread, via the time-out logic.
        result = yield deferToThread(do_nothing_async)
        self.expectThat(result, Equals(sentinel.result))

        # Here's what happened, or should have:
        # 1. do_nothing was wrapped by run_in_reactor, producing
        #    func_in_reactor.
        self.assertThat(run_in_reactor, MockCalledOnceWith(do_nothing))
        # 2. func_in_reactor was called with no arguments, because we didn't
        #    pass any, producing eventual_result.
        self.assertThat(func_in_reactor, MockCalledOnceWith())
        # 3. eventual_result.wait was called...
        if self.timeout is FOREVER:
            # ...without arguments.
            self.assertThat(wait, MockCalledOnceWith())
        else:
            # ...with the timeout we passed when we wrapped do_nothing.
            self.assertThat(wait, MockCalledOnceWith(self.timeout))


class TestSynchronousDecorator(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @synchronous
    def return_args(self, *args, **kwargs):
        return args, kwargs

    def test_in_reactor_thread(self):
        expected = MatchesException(
            AssertionError, re.escape(
                "Function return_args(...) must not be called "
                "in the reactor thread."))
        self.assertThat(self.return_args, Raises(expected))

    @inlineCallbacks
    def test_in_other_thread(self):
        def do_stuff_in_thread():
            return self.return_args(3, 4, five=5)
        # Call do_stuff_in_thread() from another thread.
        result = yield deferToThread(do_stuff_in_thread)
        # do_stuff_in_thread() ran straight through, without
        # modification. The arguments passed back match those passed in
        # from do_stuff_in_thread().
        self.assertEqual(((3, 4), {"five": 5}), result)

    def test_allows_call_in_any_thread_when_reactor_not_running(self):
        self.patch(reactor, "running", False)
        self.assertEqual(((3, 4), {"five": 5}), self.return_args(3, 4, five=5))


class TestReactorSync(MAASTestCase):
    """Tests for `reactor_sync`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test__does_what_it_claims(self):
        whence = []

        def record_whence_while_in_sync_with_reactor():
            # Sync up with the reactor three times. This increases the chance
            # that something unexpected could happen, thus breaking the test.
            # The hope is, naturally, that nothing breaks. It also means we
            # can see the reactor spinning in between; see the callLater() to
            # see how we measure this.
            for _ in xrange(3):
                with reactor_sync():
                    # Schedule a call that the reactor will make when we
                    # release sync with it.
                    reactor.callLater(0, whence.append, "reactor")
                    # Spin a bit to demonstrate that the reactor doesn't run
                    # while we're in the reactor_sync context.
                    for _ in xrange(10):
                        whence.append("thread")
                        # Sleep for a moment to allow other threads - like the
                        # reactor's thread - a chance to run. Our bet is that
                        # the reactor's thread _won't_ run because we're
                        # synchronised with it.
                        time.sleep(0.01)

        def check(_):
            self.assertEqual(
                (["thread"] * 10) + ["reactor"] +
                (["thread"] * 10) + ["reactor"] +
                (["thread"] * 10) + ["reactor"],
                whence)

        d = deferToThread(record_whence_while_in_sync_with_reactor)
        d.addCallback(check)
        return d

    def test__updates_io_thread(self):
        # We're in the reactor thread right now.
        self.assertTrue(threadable.isInIOThread())
        reactorThread = threadable.ioThread

        # The rest of this test runs in a separate thread.
        def in_thread():
            thisThread = threadable.getThreadID()
            # This is definitely not the reactor thread.
            self.assertNotEqual(thisThread, reactorThread)
            # The IO thread is still the reactor thread.
            self.assertEqual(reactorThread, threadable.ioThread)
            self.assertFalse(threadable.isInIOThread())
            # When we sync with the reactor the current thread is marked
            # as the IO thread.
            with reactor_sync():
                self.assertEqual(thisThread, threadable.ioThread)
                self.assertTrue(threadable.isInIOThread())
            # When sync is released the IO thread reverts to the
            # reactor's thread.
            self.assertEqual(reactorThread, threadable.ioThread)
            self.assertFalse(threadable.isInIOThread())

        return deferToThread(in_thread)

    def test__releases_sync_on_error(self):

        def in_thread():
            with reactor_sync():
                raise RuntimeError("Boom")

        def check(failure):
            failure.trap(RuntimeError)

        # The test is that this completes; if sync with the reactor
        # thread is not released then this will deadlock.
        return deferToThread(in_thread).addCallbacks(self.fail, check)

    def test__restores_io_thread_on_error(self):
        # We're in the reactor thread right now.
        self.assertTrue(threadable.isInIOThread())
        reactorThread = threadable.ioThread

        def in_thread():
            with reactor_sync():
                raise RuntimeError("Boom")

        def check(failure):
            failure.trap(RuntimeError)
            self.assertEqual(reactorThread, threadable.ioThread)
            self.assertTrue(threadable.isInIOThread())

        return deferToThread(in_thread).addCallbacks(self.fail, check)

    def test__does_nothing_in_the_reactor_thread(self):
        self.assertTrue(threadable.isInIOThread())
        with reactor_sync():
            self.assertTrue(threadable.isInIOThread())
        self.assertTrue(threadable.isInIOThread())

    def test__does_nothing_in_the_reactor_thread_on_error(self):
        self.assertTrue(threadable.isInIOThread())
        with ExpectedException(RuntimeError):
            with reactor_sync():
                self.assertTrue(threadable.isInIOThread())
                raise RuntimeError("I sneezed")
        self.assertTrue(threadable.isInIOThread())


class TestRetries(MAASTestCase):

    def assertRetry(
            self, clock, observed, expected_elapsed, expected_remaining,
            expected_wait):
        """Assert that the retry tuple matches the given expectations.

        Retry tuples are those returned by `retries`.
        """
        self.assertThat(observed, MatchesListwise([
            Equals(expected_elapsed),  # elapsed
            Equals(expected_remaining),  # remaining
            Equals(expected_wait),  # wait
        ]))

    def test_yields_elapsed_remaining_and_wait(self):
        # Take control of time.
        clock = Clock()

        gen_retries = retries(5, 2, clock=clock)
        # No time has passed, 5 seconds remain, and it suggests sleeping
        # for 2 seconds.
        self.assertRetry(clock, next(gen_retries), 0, 5, 2)
        # Mimic sleeping for the suggested sleep time.
        clock.advance(2)
        # Now 2 seconds have passed, 3 seconds remain, and it suggests
        # sleeping for 2 more seconds.
        self.assertRetry(clock, next(gen_retries), 2, 3, 2)
        # Mimic sleeping for the suggested sleep time.
        clock.advance(2)
        # Now 4 seconds have passed, 1 second remains, and it suggests
        # sleeping for just 1 more second.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)
        # Mimic sleeping for the suggested sleep time.
        clock.advance(1)
        # There's always a final chance to try something.
        self.assertRetry(clock, next(gen_retries), 5, 0, 0)
        # All done.
        self.assertRaises(StopIteration, next, gen_retries)

    def test_calculates_times_with_reference_to_current_time(self):
        # Take control of time.
        clock = Clock()

        gen_retries = retries(5, 2, clock=clock)
        # No time has passed, 5 seconds remain, and it suggests sleeping
        # for 2 seconds.
        self.assertRetry(clock, next(gen_retries), 0, 5, 2)
        # Mimic sleeping for 4 seconds, more than the suggested.
        clock.advance(4)
        # Now 4 seconds have passed, 1 second remains, and it suggests
        # sleeping for just 1 more second.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)
        # Don't sleep, ask again immediately, and the same answer is given.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)
        # Mimic sleeping for 100 seconds, much more than the suggested.
        clock.advance(100)
        # There's always a final chance to try something, but the elapsed and
        # remaining figures are still calculated with reference to the current
        # time. The wait time never goes below zero.
        self.assertRetry(clock, next(gen_retries), 104, -99, 0)
        # All done.
        self.assertRaises(StopIteration, next, gen_retries)


class TestPause(MAASTestCase):

    p_deferred_called = AfterPreprocessing(
        lambda d: bool(d.called), Is(True))
    p_deferred_cancelled = AfterPreprocessing(
        lambda d: d.result, MatchesAll(
            IsInstance(Failure), AfterPreprocessing(
                lambda failure: failure.value,
                IsInstance(CancelledError))))
    p_call_cancelled = AfterPreprocessing(
        lambda call: bool(call.cancelled), Is(True))
    p_call_called = AfterPreprocessing(
        lambda call: bool(call.called), Is(True))

    def test_pause_returns_a_deferred_that_fires_after_a_delay(self):
        # Take control of time.
        clock = Clock()
        wait = randint(4, 4000)

        p_call_scheduled_in_wait_seconds = AfterPreprocessing(
            lambda call: call.getTime(), Equals(wait))

        d = pause(wait, clock=clock)

        # pause() returns an uncalled deferred.
        self.assertIsInstance(d, Deferred)
        self.assertThat(d, Not(self.p_deferred_called))
        # pause() has scheduled a call to happen in `wait` seconds.
        self.assertThat(clock.getDelayedCalls(), HasLength(1))
        [delayed_call] = clock.getDelayedCalls()
        self.assertThat(delayed_call, MatchesAll(
            p_call_scheduled_in_wait_seconds,
            Not(self.p_call_cancelled),
            Not(self.p_call_called),
        ))
        # Nothing has changed right before the deadline.
        clock.advance(wait - 1)
        self.assertThat(d, Not(self.p_deferred_called))
        self.assertThat(delayed_call, MatchesAll(
            Not(self.p_call_cancelled), Not(self.p_call_called)))
        # After `wait` seconds the deferred is called.
        clock.advance(1)
        self.assertThat(d, self.p_deferred_called)
        self.assertThat(delayed_call, MatchesAll(
            Not(self.p_call_cancelled), self.p_call_called))
        # The result is unexciting.
        self.assertIsNone(d.result)

    def test_pause_can_be_cancelled(self):
        # Take control of time.
        clock = Clock()
        wait = randint(4, 4000)

        d = pause(wait, clock=clock)
        [delayed_call] = clock.getDelayedCalls()

        d.cancel()

        # The deferred has been cancelled.
        self.assertThat(d, MatchesAll(
            self.p_deferred_called, self.p_deferred_cancelled,
            first_only=True))

        # We must suppress the cancellation error here or the test suite
        # will get huffy about it.
        d.addErrback(lambda failure: None)

        # The delayed call was cancelled too.
        self.assertThat(delayed_call, MatchesAll(
            self.p_call_cancelled, Not(self.p_call_called)))


DelayedCallActive = MatchesStructure(
    cancelled=AfterPreprocessing(bool, Is(False)),
    called=AfterPreprocessing(bool, Is(False)),
)

DelayedCallCancelled = MatchesStructure(
    cancelled=AfterPreprocessing(bool, Is(True)),
    called=AfterPreprocessing(bool, Is(False)),
)

DelayedCallCalled = MatchesStructure(
    cancelled=AfterPreprocessing(bool, Is(False)),
    called=AfterPreprocessing(bool, Is(True)),
)


class TestDeferWithTimeout(MAASTestCase):

    def test__returns_Deferred_that_will_be_cancelled_after_timeout(self):
        clock = self.patch(twisted_module, "reactor", Clock())

        # Called with only a timeout, `deferWithTimeout` returns a Deferred.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout)
        self.assertThat(d, IsInstance(Deferred))
        self.assertFalse(d.called)

        # It's been scheduled for cancellation in `timeout` seconds.
        self.assertThat(clock.getDelayedCalls(), HasLength(1))
        [delayed_call] = clock.getDelayedCalls()
        self.assertThat(delayed_call, DelayedCallActive)
        self.assertThat(delayed_call, MatchesStructure.byEquality(
            time=timeout, func=d.cancel, args=(), kw={}))

        # Once the timeout is reached, the delayed call is called, and this
        # cancels `d`. The default canceller for Deferred errbacks with
        # CancelledError.
        clock.advance(timeout)
        self.assertThat(delayed_call, DelayedCallCalled)
        self.assertRaises(CancelledError, extract_result, d)

    def test__returns_Deferred_that_wont_be_cancelled_if_called(self):
        clock = self.patch(twisted_module, "reactor", Clock())

        # Called without a function argument, `deferWithTimeout` returns a new
        # Deferred, and schedules it to be cancelled in `timeout` seconds.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout)
        [delayed_call] = clock.getDelayedCalls()

        # Advance some amount of time to simulate something happening.
        clock.advance(5)
        # The timeout call is still in place.
        self.assertThat(delayed_call, DelayedCallActive)

        d.callback(sentinel.result)
        # After calling d the timeout call has been cancelled.
        self.assertThat(delayed_call, DelayedCallCancelled)
        # The result has been safely passed on.
        self.assertThat(extract_result(d), Is(sentinel.result))

    def test__returns_Deferred_that_wont_be_cancelled_if_errored(self):
        clock = self.patch(twisted_module, "reactor", Clock())

        # Called without a function argument, `deferWithTimeout` returns a new
        # Deferred, and schedules it to be cancelled in `timeout` seconds.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout)
        [delayed_call] = clock.getDelayedCalls()

        # Advance some amount of time to simulate something happening, but
        # less than the timeout.
        clock.advance(timeout - 1)
        # The timeout call is still in place.
        self.assertThat(delayed_call, DelayedCallActive)

        error = RuntimeError()
        d.errback(error)
        # After calling d the timeout call has been cancelled.
        self.assertThat(delayed_call, DelayedCallCancelled)
        # The error has been passed safely on.
        self.assertRaises(RuntimeError, extract_result, d)

    def test__calls_given_function(self):
        clock = self.patch(twisted_module, "reactor", Clock())

        class OurDeferred(Deferred):
            """A Deferred subclass that we use as a marker."""

        # Any given function is called via `maybeDeferred`. In this case, we
        # get an instance of our marker class back because it is a Deferred.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout, OurDeferred)
        self.assertThat(d, IsInstance(OurDeferred))
        self.assertFalse(d.called)

        # Just as with the non-function form, it's been scheduled for
        # cancellation in `timeout` seconds.
        self.assertThat(clock.getDelayedCalls(), HasLength(1))
        [delayed_call] = clock.getDelayedCalls()
        self.assertThat(delayed_call, DelayedCallActive)
        self.assertThat(delayed_call, MatchesStructure.byEquality(
            time=timeout, func=d.cancel, args=(), kw={}))

        # Once the timeout is reached, the delayed call is called, and this
        # cancels `d`. The default canceller for Deferred errbacks with
        # CancelledError.
        clock.advance(timeout)
        self.assertThat(delayed_call, DelayedCallCalled)
        self.assertRaises(CancelledError, extract_result, d)

    def test__calls_given_function_and_always_returns_Deferred(self):
        clock = self.patch(twisted_module, "reactor", Clock())

        def do_something(a, *b, **c):
            return do_something, a, b, c

        # Any given function is called via `maybeDeferred`. In this case, we
        # get an already-called Deferred, because `do_something` is
        # synchronous.
        timeout = randint(10, 100)
        d = deferWithTimeout(
            timeout, do_something, sentinel.a, sentinel.b, c=sentinel.c)
        self.assertThat(d, IsInstance(Deferred))
        self.assertEqual(
            (do_something, sentinel.a, (sentinel.b,), {"c": sentinel.c}),
            extract_result(d))

        # The timeout has already been cancelled.
        self.assertThat(clock.getDelayedCalls(), Equals([]))


class TestCallOut(MAASTestCase):
    """Tests for `callOut`."""

    def test__without_arguments(self):
        func = Mock()
        func_callout = callOut(func)
        # The result is passed through untouched.
        self.assertThat(func_callout(sentinel.result), Is(sentinel.result))
        self.assertThat(func, MockCalledOnceWith())

    def test__with_arguments(self):
        func = Mock()
        func_callout = callOut(func, sentinel.a, sentinel.b, c=sentinel.c)
        # The result is passed through untouched.
        self.assertThat(func_callout(sentinel.result), Is(sentinel.result))
        self.assertThat(func, MockCalledOnceWith(
            sentinel.a, sentinel.b, c=sentinel.c))

    def test__does_not_suppress_errors(self):
        func_callout = callOut(operator.div, 0, 0)
        self.assertRaises(ZeroDivisionError, func_callout, sentinel.result)
