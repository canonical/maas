# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from functools import partial
import io
from itertools import cycle
import operator
import os
from random import randint, random
import re
import signal
import sys
import threading
from unittest import mock, TestCase
from unittest.mock import ANY, Mock, sentinel

from crochet import EventualResult
from testscenarios import multiply_scenarios
from testtools.content import content_from_stream
from twisted import internet
from twisted.internet import address, reactor
from twisted.internet.defer import (
    AlreadyCalledError,
    CancelledError,
    Deferred,
    DeferredSemaphore,
    inlineCallbacks,
    succeed,
)
from twisted.internet.error import ProcessDone, ProcessTerminated
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.task import Clock
from twisted.internet.threads import deferToThread, deferToThreadPool
from twisted.python import context, threadable
from twisted.python.failure import Failure
from twisted.web.test import requesthelper

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import extract_result, TwistedLoggerFixture
from provisioningserver.utils import twisted as twisted_module
from provisioningserver.utils.twisted import (
    asynchronous,
    call,
    callInReactor,
    callInReactorWithTimeout,
    callOut,
    callOutToThread,
    DeferredValue,
    deferToNewThread,
    deferWithTimeout,
    FOREVER,
    IAsynchronous,
    ISynchronous,
    LONGTIME,
    makeDeferredWithProcessProtocol,
    pause,
    reducedWebLogFormatter,
    retries,
    RPCFetcher,
    suppress,
    synchronous,
    terminateProcess,
    threadDeferred,
    ThreadPool,
    ThreadPoolLimiter,
    ThreadUnpool,
)

TIMEOUT = get_testing_timeout()


def return_args(*args, **kwargs):
    return args, kwargs


class TestAsynchronousDecorator(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_calls_in_current_thread_when_current_thread_is_reactor(self):
        result = asynchronous(return_args)(1, 2, three=3)
        self.assertEqual(((1, 2), {"three": 3}), result)

    def test_calls_in_current_thread_when_io_thread_is_not_set(self):
        # Patch ioThread such that isInIOThread() returns False. It will
        # return False for every thread too, so asynchronous() explicitly
        # checks ioThread. It can be unset as twistd starts an application, so
        # we assume we're in the reactor thread anyway.
        self.patch(threadable, "ioThread", None)
        self.assertFalse(threadable.isInIOThread())
        result = asynchronous(return_args)(1, 2, three=3)
        self.assertEqual(((1, 2), {"three": 3}), result)

    @inlineCallbacks
    def test_calls_into_reactor_when_current_thread_is_not_reactor(self):
        def do_stuff_in_thread():
            result = asynchronous(return_args)(3, 4, five=5)
            self.assertIsInstance(result, EventualResult)
            return result.wait(TIMEOUT)

        # Call do_stuff_in_thread() from another thread.
        result = yield deferToThread(do_stuff_in_thread)
        # do_stuff_in_thread() waited for the result of return_args().
        # The arguments passed back match those passed in from
        # do_stuff_in_thread().
        self.assertEqual(((3, 4), {"five": 5}), result)

    def test_provides_marker_interface(self):
        self.assertFalse(IAsynchronous.providedBy(return_args))
        self.assertTrue(IAsynchronous.providedBy(asynchronous(return_args)))


def noop():
    pass


class TestThreadDeferred(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_thread_deferred(self):
        @threadDeferred
        def func():
            return threading.get_ident()

        ident = yield func()
        self.assertNotEqual(ident, threading.get_ident())


class TestAsynchronousDecoratorWithTimeout(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_timeout_cannot_be_None(self):
        self.assertRaises(ValueError, asynchronous, noop, timeout=None)

    def test_timeout_cannot_be_negative(self):
        self.assertRaises(ValueError, asynchronous, noop, timeout=-1)

    def test_timeout_can_be_int(self):
        self.assertTrue(callable(asynchronous(noop, timeout=1)))

    def test_timeout_can_be_long(self):
        self.assertTrue(callable(asynchronous(noop, timeout=1)))

    def test_timeout_can_be_float(self):
        self.assertTrue(callable(asynchronous(noop, timeout=1.0)))

    def test_timeout_can_be_forever(self):
        self.assertTrue(callable(asynchronous(noop, timeout=FOREVER)))


class TestAsynchronousDecoratorWithTimeoutDefined(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    scenarios = (
        ("finite", {"timeout": random()}),
        ("forever", {"timeout": FOREVER}),
    )

    def test_in_reactor_thread(self):
        return_args_async = asynchronous(return_args, timeout=self.timeout)
        result = return_args_async(1, 2, three=3)
        self.assertEqual(((1, 2), {"three": 3}), result)

    @inlineCallbacks
    def test_in_other_thread(self):
        return_args_async = asynchronous(return_args, timeout=self.timeout)
        # Call self.return_args from another thread.
        result = yield deferToThread(return_args_async, 3, 4, five=5)
        # The arguments passed back match those passed in.
        self.assertEqual(((3, 4), {"five": 5}), result)

    @inlineCallbacks
    def test_passes_timeout_to_wait(self):
        # These mocks are going to help us tell a story of a timeout.
        run_in_reactor = self.patch(twisted_module, "run_in_reactor")
        func_in_reactor = run_in_reactor.return_value
        eventual_result = func_in_reactor.return_value
        wait = eventual_result.wait
        wait.return_value = sentinel.result

        # Our placeholder function, and its wrapped version.
        def do_nothing():
            pass

        do_nothing_async = asynchronous(do_nothing, timeout=self.timeout)

        # Call our wrapped function in a thread so that the wrapper calls back
        # into the IO thread, via the time-out logic.
        result = yield deferToThread(do_nothing_async)
        self.assertEqual(result, sentinel.result)

        # Here's what happened, or should have:
        # 1. do_nothing was wrapped by run_in_reactor, producing
        #    func_in_reactor.
        run_in_reactor.assert_called_once_with(do_nothing)
        # 2. func_in_reactor was called with no arguments, because we didn't
        #    pass any, producing eventual_result.
        func_in_reactor.assert_called_once_with()
        # 3. eventual_result.wait was called...
        if self.timeout is FOREVER:
            # ...without arguments.
            wait.assert_called_once_with(LONGTIME)
        else:
            # ...with the timeout we passed when we wrapped do_nothing.
            wait.assert_called_once_with(self.timeout)


class TestSynchronousDecorator(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @synchronous
    def return_args(self, *args, **kwargs):
        return args, kwargs

    def test_in_reactor_thread(self):
        with self.assertRaisesRegex(
            AssertionError,
            re.escape(
                "Function return_args(...) must not be called in the reactor thread."
            ),
        ):
            self.return_args()

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

    def test_provides_marker_interface(self):
        self.assertFalse(ISynchronous.providedBy(return_args))
        self.assertTrue(ISynchronous.providedBy(synchronous(return_args)))


class TestSynchronousDecoratorSychronously(MAASTestCase):
    """Test `synchronous` outside of the reactor thread."""

    def assertRaises(self, *args, **kwargs):
        return TestCase.assertRaises(self, *args, **kwargs)

    def test_raises_TypeError_when_call_returns_Deferred(self):
        @synchronous
        def deferSomething(*args, **kwargs):
            return Deferred()

        a, b = factory.make_name("a"), factory.make_name("b")
        with self.assertRaises(TypeError) as cm:
            deferSomething(a, b=b)

        self.assertEqual(
            str(cm.exception),
            "Synchronous call returned a Deferred: %s(%r, b=%r)"
            % (deferSomething.__qualname__, a, b),
        )

    def test_raises_TypeError_when_callable_returns_Deferred(self):
        class Something:
            def __call__(self, *args, **kwargs):
                return Deferred()

        something = synchronous(Something())
        a, b = factory.make_name("a"), factory.make_name("b")
        with self.assertRaises(TypeError) as cm:
            something(a, b=b)
        self.assertEqual(
            str(cm.exception),
            "Synchronous call returned a Deferred: %s(%r, b=%r)"
            % (Something.__qualname__, a, b),
        )


class TestSuppress(MAASTestCase):
    """Tests for `suppress`."""

    def test_suppresses_given_exception(self):
        error_type = factory.make_exception_type()
        failure = Failure(error_type())
        self.assertIsNone(suppress(failure, error_type))

    def test_does_not_suppress_other_exceptions(self):
        error_type = factory.make_exception_type()
        failure = Failure(factory.make_exception())
        self.assertIs(suppress(failure, error_type), failure)

    def test_returns_instead_value_when_suppressing(self):
        error_type = factory.make_exception_type()
        failure = Failure(error_type())
        self.assertIs(
            suppress(failure, error_type, instead=sentinel.instead),
            sentinel.instead,
        )


class TestRetries(MAASTestCase):
    def assertRetry(
        self,
        clock,
        observed,
        expected_elapsed,
        expected_remaining,
        expected_wait,
    ):
        """Assert that the retry tuple matches the given expectations.

        Retry tuples are those returned by `retries`.
        """
        elapsed, remaining, wait = observed
        self.assertEqual(elapsed, expected_elapsed)
        self.assertEqual(remaining, expected_remaining)
        self.assertEqual(wait, expected_wait)

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

    def test_captures_start_time_when_called(self):
        # Take control of time.
        clock = Clock()

        gen_retries = retries(5, 2, clock=clock)
        clock.advance(4)
        # 4 seconds have passed, so 1 second remains, and it suggests sleeping
        # for 1 second.
        self.assertRetry(clock, next(gen_retries), 4, 1, 1)

    def test_intervals_can_be_an_iterable(self):
        # Take control of time.
        clock = Clock()
        # Use intervals of 1s, 2s, 3, and then back to 1s.
        intervals = cycle((1.0, 2.0, 3.0))

        gen_retries = retries(5, intervals, clock=clock)
        # No time has passed, 5 seconds remain, and it suggests sleeping
        # for 1 second, then 2, then 3, then 1 again.
        self.assertRetry(clock, next(gen_retries), 0, 5, 1)
        self.assertRetry(clock, next(gen_retries), 0, 5, 2)
        self.assertRetry(clock, next(gen_retries), 0, 5, 3)
        self.assertRetry(clock, next(gen_retries), 0, 5, 1)
        # Mimic sleeping for 3.5 seconds, more than the suggested.
        clock.advance(3.5)
        # Now 3.5 seconds have passed, 1.5 seconds remain, and it suggests
        # sleeping for 1.5 seconds, 0.5 less than the next expected interval
        # of 2.0 seconds.
        self.assertRetry(clock, next(gen_retries), 3.5, 1.5, 1.5)
        # Don't sleep, ask again immediately, and the same answer is given.
        self.assertRetry(clock, next(gen_retries), 3.5, 1.5, 1.5)
        # Don't sleep, ask again immediately, and 1.0 seconds is given,
        # because we're back to the 1.0 second interval.
        self.assertRetry(clock, next(gen_retries), 3.5, 1.5, 1.0)
        # Mimic sleeping for 100 seconds, much more than the suggested.
        clock.advance(100)
        # There's always a final chance to try something, but the elapsed and
        # remaining figures are still calculated with reference to the current
        # time. The wait time never goes below zero.
        self.assertRetry(clock, next(gen_retries), 103.5, -98.5, 0.0)
        # All done.
        self.assertRaises(StopIteration, next, gen_retries)


class TestPause(MAASTestCase):
    def test_pause_returns_a_deferred_that_fires_after_a_delay(self):
        # Take control of time.
        clock = Clock()
        wait = randint(4, 4000)

        d = pause(wait, clock=clock)

        # pause() returns an uncalled deferred.
        self.assertIsInstance(d, Deferred)
        self.assertFalse(d.called)
        # pause() has scheduled a call to happen in `wait` seconds.
        self.assertEqual(len(clock.getDelayedCalls()), 1)
        [delayed_call] = clock.getDelayedCalls()
        self.assertEqual(delayed_call.getTime(), wait)
        self.assertFalse(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)

        # Nothing has changed right before the deadline.
        clock.advance(wait - 1)
        self.assertFalse(d.called)
        self.assertFalse(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)

        # After `wait` seconds the deferred is called.
        clock.advance(1)
        self.assertTrue(d.called)
        self.assertFalse(delayed_call.cancelled)
        self.assertTrue(delayed_call.called)

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
        self.assertTrue(d.called)
        self.assertIsInstance(d.result, Failure)
        self.assertIsInstance(d.result.value, CancelledError)

        # We must suppress the cancellation error here or the test suite
        # will get huffy about it.
        d.addErrback(lambda failure: None)

        # The delayed call was cancelled too.
        self.assertTrue(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)


class TestDeferWithTimeout(MAASTestCase):
    def test_returns_Deferred_that_will_be_cancelled_after_timeout(self):
        clock = self.patch(internet, "reactor", Clock())

        # Called with only a timeout, `deferWithTimeout` returns a Deferred.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout)
        self.assertIsInstance(d, Deferred)
        self.assertFalse(d.called)

        # It's been scheduled for cancellation in `timeout` seconds.
        self.assertEqual(len(clock.getDelayedCalls()), 1)
        [delayed_call] = clock.getDelayedCalls()
        self.assertFalse(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)

        self.assertEqual(delayed_call.time, timeout)
        self.assertEqual(delayed_call.func, d.cancel)
        self.assertEqual(delayed_call.args, ())
        self.assertEqual(delayed_call.kw, {})

        # Once the timeout is reached, the delayed call is called, and this
        # cancels `d`. The default canceller for Deferred errbacks with
        # CancelledError.
        clock.advance(timeout)
        self.assertFalse(delayed_call.cancelled)
        self.assertTrue(delayed_call.called)
        self.assertRaises(CancelledError, extract_result, d)

    def test_returns_Deferred_that_wont_be_cancelled_if_called(self):
        clock = self.patch(internet, "reactor", Clock())

        # Called without a function argument, `deferWithTimeout` returns a new
        # Deferred, and schedules it to be cancelled in `timeout` seconds.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout)
        [delayed_call] = clock.getDelayedCalls()

        # Advance some amount of time to simulate something happening.
        clock.advance(5)
        # The timeout call is still in place.
        self.assertFalse(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)

        d.callback(sentinel.result)
        # After calling d the timeout call has been cancelled.
        self.assertTrue(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)
        # The result has been safely passed on.
        self.assertIs(extract_result(d), sentinel.result)

    def test_returns_Deferred_that_wont_be_cancelled_if_errored(self):
        clock = self.patch(internet, "reactor", Clock())

        # Called without a function argument, `deferWithTimeout` returns a new
        # Deferred, and schedules it to be cancelled in `timeout` seconds.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout)
        [delayed_call] = clock.getDelayedCalls()

        # Advance some amount of time to simulate something happening, but
        # less than the timeout.
        clock.advance(timeout - 1)
        # The timeout call is still in place.
        self.assertFalse(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)

        error = RuntimeError()
        d.errback(error)
        # After calling d the timeout call has been cancelled.
        self.assertTrue(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)
        # The error has been passed safely on.
        self.assertRaises(RuntimeError, extract_result, d)

    def test_calls_given_function(self):
        clock = self.patch(internet, "reactor", Clock())

        class OurDeferred(Deferred):
            """A Deferred subclass that we use as a marker."""

        # Any given function is called via `maybeDeferred`. In this case, we
        # get an instance of our marker class back because it is a Deferred.
        timeout = randint(10, 100)
        d = deferWithTimeout(timeout, OurDeferred)
        self.assertIsInstance(d, OurDeferred)
        self.assertFalse(d.called)

        # Just as with the non-function form, it's been scheduled for
        # cancellation in `timeout` seconds.
        self.assertEqual(len(clock.getDelayedCalls()), 1)
        [delayed_call] = clock.getDelayedCalls()
        self.assertFalse(delayed_call.cancelled)
        self.assertFalse(delayed_call.called)
        self.assertEqual(delayed_call.time, timeout)
        self.assertEqual(delayed_call.func, d.cancel)
        self.assertEqual(delayed_call.args, ())
        self.assertEqual(delayed_call.kw, {})

        # Once the timeout is reached, the delayed call is called, and this
        # cancels `d`. The default canceller for Deferred errbacks with
        # CancelledError.
        clock.advance(timeout)
        self.assertFalse(delayed_call.cancelled)
        self.assertTrue(delayed_call.called)

        self.assertRaises(CancelledError, extract_result, d)

    def test_calls_given_function_and_always_returns_Deferred(self):
        clock = self.patch(internet, "reactor", Clock())

        def do_something(a, *b, **c):
            return do_something, a, b, c

        # Any given function is called via `maybeDeferred`. In this case, we
        # get an already-called Deferred, because `do_something` is
        # synchronous.
        timeout = randint(10, 100)
        d = deferWithTimeout(
            timeout, do_something, sentinel.a, sentinel.b, c=sentinel.c
        )
        self.assertIsInstance(d, Deferred)
        self.assertEqual(
            (do_something, sentinel.a, (sentinel.b,), {"c": sentinel.c}),
            extract_result(d),
        )

        # The timeout has already been cancelled.
        self.assertEqual([], clock.getDelayedCalls())


class TestCall(MAASTestCase):
    """Tests for `call`."""

    def test_without_arguments(self):
        func = Mock(return_value=sentinel.something)
        # The result going in is discarded; func's result is passed on.
        d = call(sentinel.result, func)
        self.assertIs(extract_result(d), sentinel.something)
        func.mock_called_once_with()

    def test_with_arguments(self):
        func = Mock(return_value=sentinel.something)
        # The result going in is discarded; func's result is passed on.
        d = call(sentinel.r, func, sentinel.a, sentinel.b, c=sentinel.c)
        self.assertIs(extract_result(d), sentinel.something)
        func.mock_called_once_with(sentinel.a, sentinel.b, c=sentinel.c)

    def test_does_not_suppress_errors(self):
        d = call(sentinel.result, operator.truediv, 0, 0)
        self.assertRaises(ZeroDivisionError, extract_result, d)


class TestCallOut(MAASTestCase):
    """Tests for `callOut`."""

    def test_without_arguments(self):
        func = Mock()
        # The result is passed through untouched.
        d = callOut(sentinel.result, func)
        self.assertIs(extract_result(d), sentinel.result)
        func.assert_called_once_with()

    def test_with_arguments(self):
        func = Mock()
        # The result is passed through untouched.
        d = callOut(sentinel.r, func, sentinel.a, sentinel.b, c=sentinel.c)
        self.assertIs(extract_result(d), sentinel.r)
        func.mock_called_once_with(sentinel.a, sentinel.b, c=sentinel.c)

    def test_does_not_suppress_errors(self):
        d = callOut(sentinel.result, operator.truediv, 0, 0)
        self.assertRaises(ZeroDivisionError, extract_result, d)


class TestCallOutToThread(MAASTestCase):
    """Tests for `callOutToThread`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_without_arguments(self):
        func = Mock()
        # The result is passed through untouched.
        result = yield callOutToThread(sentinel.result, func)
        self.assertIs(result, sentinel.result)
        func.assert_called_once_with()

    @inlineCallbacks
    def test_with_arguments(self):
        func = Mock()
        # The result is passed through untouched.
        result = yield callOutToThread(
            sentinel.r, func, sentinel.a, sentinel.b, c=sentinel.c
        )
        self.assertIs(result, sentinel.r)
        func.mock_called_once_with(sentinel.a, sentinel.b, c=sentinel.c)

    @inlineCallbacks
    def test_does_not_suppress_errors(self):
        with TestCase.assertRaises(self, ZeroDivisionError):
            yield callOutToThread(sentinel.result, operator.truediv, 0, 0)

    @inlineCallbacks
    def test_defers_to_thread(self):
        threads = {threading.current_thread()}

        def captureThread():
            threads.add(threading.current_thread())

        yield callOutToThread(None, captureThread)
        self.assertEqual(len(threads), 2, threads)


class TestCallInReactor(MAASTestCase):
    """Tests for `callInReactor`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def returnThreadIdent(self, *_, **__):
        return threading.get_ident()

    def test_without_arguments_from_reactor(self):
        func = Mock(side_effect=self.returnThreadIdent)
        result = callInReactor(func)
        self.assertEqual(threading.get_ident(), result)
        func.assert_called_once_with()

    @inlineCallbacks
    def test_without_arguments_from_thread(self):
        func = Mock(side_effect=self.returnThreadIdent)
        result = yield deferToNewThread(callInReactor, func)
        self.assertEqual(threading.get_ident(), result)
        func.assert_called_once_with()

    def test_with_arguments_in_reactor(self):
        func = Mock(side_effect=self.returnThreadIdent)
        result = callInReactor(func, sentinel.a, b=sentinel.b)
        self.assertEqual(threading.get_ident(), result)
        func.assert_called_once_with(sentinel.a, b=sentinel.b)

    @inlineCallbacks
    def test_with_arguments_in_thread(self):
        func = Mock(side_effect=self.returnThreadIdent)
        result = yield deferToNewThread(
            callInReactor, func, sentinel.a, b=sentinel.b
        )
        self.assertEqual(threading.get_ident(), result)
        func.assert_called_once_with(sentinel.a, b=sentinel.b)


class TestCallInReactorErrors(MAASTestCase):
    """Tests for error behaviour in `callInReactor`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def assertRaises(self, *args, **kwargs):
        return TestCase.assertRaises(self, *args, **kwargs)

    def test_propagates_exceptions_in_reactor(self):
        with self.assertRaises(ZeroDivisionError):
            callInReactor(operator.truediv, 0, 0)

    @inlineCallbacks
    def test_propagates_exceptions_in_thread(self):
        with self.assertRaises(ZeroDivisionError):
            yield deferToNewThread(callInReactor, operator.truediv, 0, 0)


class TestCallInReactorWithTimeout(MAASTestCase):
    """Tests for `callInReactorWithTimeout`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.deferWithTimeout = self.patch(twisted_module, "deferWithTimeout")
        self.deferWithTimeout.side_effect = self.returnThreadIdent

    def returnThreadIdent(self, *_, **__):
        return threading.get_ident()

    def test_without_arguments_from_reactor(self):
        result = callInReactorWithTimeout(sentinel.timeout, sentinel.func)
        self.assertEqual(threading.get_ident(), result)
        self.deferWithTimeout.assert_called_once_with(
            sentinel.timeout, sentinel.func
        )

    @inlineCallbacks
    def test_without_arguments_from_thread(self):
        result = yield deferToNewThread(
            callInReactorWithTimeout, sentinel.timeout, sentinel.func
        )
        self.assertEqual(threading.get_ident(), result)
        self.deferWithTimeout.assert_called_once_with(
            sentinel.timeout, sentinel.func
        )

    def test_with_arguments_in_reactor(self):
        result = callInReactorWithTimeout(
            sentinel.timeout, sentinel.func, sentinel.a, b=sentinel.b
        )
        self.assertEqual(threading.get_ident(), result)
        self.deferWithTimeout.assert_called_once_with(
            sentinel.timeout, sentinel.func, sentinel.a, b=sentinel.b
        )

    @inlineCallbacks
    def test_with_arguments_in_thread(self):
        result = yield deferToNewThread(
            callInReactorWithTimeout,
            sentinel.timeout,
            sentinel.func,
            sentinel.a,
            b=sentinel.b,
        )
        self.assertEqual(threading.get_ident(), result)
        self.deferWithTimeout.assert_called_once_with(
            sentinel.timeout, sentinel.func, sentinel.a, b=sentinel.b
        )


class TestCallInReactorWithTimeoutErrors(MAASTestCase):
    """Tests for error behaviour in `callInReactorWithTimeout`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def assertRaises(self, *args, **kwargs):
        return TestCase.assertRaises(self, *args, **kwargs)

    @inlineCallbacks
    def test_propagates_exceptions_in_reactor(self):
        with self.assertRaises(ZeroDivisionError):
            yield callInReactorWithTimeout(5.0, operator.truediv, 0, 0)

    @inlineCallbacks
    def test_propagates_exceptions_in_thread(self):
        with self.assertRaises(ZeroDivisionError):
            yield deferToNewThread(
                callInReactorWithTimeout, 5.0, operator.truediv, 0, 0
            )


class TestDeferredValue(MAASTestCase):
    """Tests for `DeferredValue`."""

    def test_create(self):
        dvalue = DeferredValue()
        self.assertEqual(dvalue.waiters, set())
        self.assertIsNone(dvalue.capturing)
        self.assertIsNone(dvalue.observing)

    def test_get_returns_a_Deferred(self):
        dvalue = DeferredValue()
        self.assertIsInstance(dvalue.get(), Deferred)

    def test_get_returns_a_Deferred_with_a_timeout(self):
        clock = self.patch(internet, "reactor", Clock())
        dvalue = DeferredValue()
        waiter = dvalue.get(10)
        self.assertIsInstance(waiter, Deferred)
        self.assertFalse(waiter.called)
        clock.advance(9)
        self.assertIsInstance(waiter, Deferred)
        self.assertFalse(waiter.called)
        clock.advance(1)
        self.assertRaises(CancelledError, extract_result, waiter)

    def test_set_notifies_all_waiters(self):
        dvalue = DeferredValue()
        waiter1 = dvalue.get()
        waiter2 = dvalue.get()
        dvalue.set(sentinel.value)
        self.assertIs(extract_result(waiter1), sentinel.value)
        self.assertIs(extract_result(waiter2), sentinel.value)

    def test_set_notifies_all_waiters_that_have_not_timed_out(self):
        clock = self.patch(internet, "reactor", Clock())
        dvalue = DeferredValue()
        waiter0 = dvalue.get()
        waiter1 = dvalue.get(1)
        waiter2 = dvalue.get(3)
        clock.advance(2)
        dvalue.set(sentinel.value)
        self.assertIs(extract_result(waiter0), sentinel.value)
        self.assertIs(extract_result(waiter2), sentinel.value)
        self.assertRaises(CancelledError, extract_result, waiter1)

    def test_set_clears_and_cancels_capturing(self):
        dvalue = DeferredValue()
        source = Deferred()
        dvalue.capturing = source
        dvalue.set(sentinel.value)
        self.assertIsNone(dvalue.capturing)
        self.assertRaises(CancelledError, extract_result, source)

    def test_set_clears_observing(self):
        dvalue = DeferredValue()
        source = Deferred()
        dvalue.observing = source
        dvalue.set(sentinel.value)
        self.assertIsNone(dvalue.observing)
        self.assertFalse(source.called)

    def test_get_after_set_returns_the_value(self):
        dvalue = DeferredValue()
        dvalue.set(sentinel.value)
        waiter = dvalue.get()
        self.assertIs(extract_result(waiter), sentinel.value)

    def test_get_can_be_cancelled(self):
        dvalue = DeferredValue()
        waiter = dvalue.get()
        waiter.cancel()
        self.assertRaises(CancelledError, extract_result, waiter)
        self.assertEqual(set(), dvalue.waiters)

    def test_set_can_only_be_called_once(self):
        dvalue = DeferredValue()
        dvalue.set(sentinel.value)
        self.assertRaises(AlreadyCalledError, dvalue.set, sentinel.foobar)

    def test_cancel_stops_everything(self):
        dvalue = DeferredValue()
        waiter = dvalue.get()
        dvalue.cancel()
        self.assertRaises(CancelledError, extract_result, waiter)
        self.assertRaises(CancelledError, extract_result, dvalue.get())
        self.assertRaises(AlreadyCalledError, dvalue.set, sentinel.value)

    def test_cancel_can_be_called_multiple_times(self):
        dvalue = DeferredValue()
        dvalue.cancel()
        self.assertRaises(AlreadyCalledError, dvalue.set, sentinel.value)
        dvalue.cancel()
        self.assertRaises(AlreadyCalledError, dvalue.set, sentinel.value)

    def test_cancel_does_nothing_if_value_already_set(self):
        dvalue = DeferredValue()
        dvalue.set(sentinel.value)
        dvalue.cancel()
        self.assertEqual(sentinel.value, extract_result(dvalue.get()))

    def test_cancel_clears_and_cancels_capturing(self):
        dvalue = DeferredValue()
        source = Deferred()
        dvalue.capturing = source
        dvalue.cancel()
        self.assertIsNone(dvalue.capturing)
        self.assertRaises(CancelledError, extract_result, source)

    def test_cancel_clears_observing(self):
        dvalue = DeferredValue()
        source = Deferred()
        dvalue.observing = source
        dvalue.cancel()
        self.assertIsNone(dvalue.observing)
        self.assertFalse(source.called)

    def test_set_exception_results_in_a_callback(self):
        exception = factory.make_exception()
        dvalue = DeferredValue()
        dvalue.set(exception)
        self.assertIs(exception, dvalue.value)

    def test_set_failure_results_in_an_errback(self):
        exception_type = factory.make_exception_type()
        dvalue = DeferredValue()
        dvalue.set(Failure(exception_type()))
        self.assertRaises(exception_type, extract_result, dvalue.get())

    def test_fail_results_in_an_errback(self):
        exception_type = factory.make_exception_type()
        dvalue = DeferredValue()
        dvalue.fail(exception_type())
        self.assertRaises(exception_type, extract_result, dvalue.get())

    def test_fail_None_results_in_an_errback_with_current_exception(self):
        exception_type = factory.make_exception_type()
        dvalue = DeferredValue()
        try:
            raise exception_type()
        except exception_type:
            dvalue.fail()
        self.assertRaises(exception_type, extract_result, dvalue.get())

    def test_fail_can_only_be_called_once(self):
        exception = factory.make_exception()
        dvalue = DeferredValue()
        dvalue.fail(exception)
        self.assertRaises(AlreadyCalledError, dvalue.fail, exception)

    def test_value_is_not_available_until_set(self):
        dvalue = DeferredValue()
        self.assertRaises(AttributeError, lambda: dvalue.value)

    def test_capture_captures_callback(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.capture(d)
        waiter = dvalue.get()
        self.assertIsInstance(waiter, Deferred)
        self.assertFalse(waiter.called)
        d.callback(sentinel.result)
        self.assertEqual(sentinel.result, extract_result(waiter))
        self.assertIsNone(extract_result(d))

    def test_capture_captures_errback(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.capture(d)
        waiter = dvalue.get()
        self.assertIsInstance(waiter, Deferred)
        self.assertFalse(waiter.called)
        exception = factory.make_exception()
        d.errback(exception)
        self.assertRaises(type(exception), extract_result, waiter)
        self.assertIsNone(extract_result(d))

    def test_capture_records_source_as_capturing_attribute(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.capture(d)
        self.assertIs(d, dvalue.capturing)

    def test_capture_can_only_be_called_once(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.capture(d)
        self.assertRaises(AlreadyCalledError, dvalue.capture, d)
        # It's not possible to call observe() once capture() has been called.
        self.assertRaises(AlreadyCalledError, dvalue.observe, d)

    def test_capture_cannot_be_called_once_value_is_set(self):
        dvalue = DeferredValue()
        dvalue.set(sentinel.value)
        self.assertRaises(AlreadyCalledError, dvalue.capture, sentinel.unused)

    def test_observe_observes_callback(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.observe(d)
        waiter = dvalue.get()
        self.assertIsInstance(waiter, Deferred)
        self.assertFalse(waiter.called)
        d.callback(sentinel.result)
        self.assertEqual(sentinel.result, extract_result(waiter))
        self.assertEqual(sentinel.result, extract_result(d))

    def test_observe_observes_errback(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.observe(d)
        waiter = dvalue.get()
        self.assertIsInstance(waiter, Deferred)
        self.assertFalse(waiter.called)
        exception = factory.make_exception()
        d.errback(exception)
        self.assertRaises(type(exception), extract_result, waiter)
        self.assertRaises(type(exception), extract_result, d)

    def test_observe_records_source_as_observing_attribute(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.observe(d)
        self.assertIs(d, dvalue.observing)

    def test_observe_can_only_be_called_once(self):
        dvalue = DeferredValue()
        d = Deferred()
        dvalue.observe(d)
        self.assertRaises(AlreadyCalledError, dvalue.observe, d)
        # It's not possible to call capture() once observe() has been called.
        self.assertRaises(AlreadyCalledError, dvalue.capture, d)

    def test_observe_cannot_be_called_once_value_is_set(self):
        dvalue = DeferredValue()
        dvalue.set(sentinel.value)
        self.assertRaises(AlreadyCalledError, dvalue.observe, sentinel.unused)

    def test_isSet_is_False_when_there_is_no_value(self):
        dvalue = DeferredValue()
        self.assertFalse(dvalue.isSet)

    def test_isSet_is_True_when_there_is_a_value(self):
        dvalue = DeferredValue()
        dvalue.set(sentinel.foobar)
        self.assertTrue(dvalue.isSet)

    def test_isSet_is_True_when_there_is_a_failure(self):
        dvalue = DeferredValue()
        dvalue.fail(factory.make_exception())
        self.assertTrue(dvalue.isSet)


class TestRPCFetcher(MAASTestCase):
    """Tests for `RPCFetcher`."""

    def setUp(self):
        super().setUp()
        self.fake_command = Mock(__name__="Command")

    def test_call_returns_deferred(self):
        client = Mock()
        fetcher = RPCFetcher()
        d = fetcher(client, self.fake_command, test=sentinel.kwarg_test)

        self.assertIsInstance(d, Deferred)
        client.assert_called_once_with(
            self.fake_command, test=sentinel.kwarg_test
        )

    def test_deferred_fires_when_client_completes(self):
        client = Mock()
        client.return_value = Deferred()

        fetcher = RPCFetcher()
        d = fetcher(client, self.fake_command, test=sentinel.kwarg_test)

        self.assertIsInstance(d, Deferred)
        self.assertFalse(d.called)
        client.return_value.callback(sentinel.content)
        self.assertTrue(d.called)
        self.assertIs(extract_result(d), sentinel.content)
        self.assertNotIn(client, fetcher.pending)

    def test_concurrent_gets_become_related(self):
        client = Mock()
        client.return_value = Deferred()

        fetcher = RPCFetcher()
        d1 = fetcher(client, self.fake_command, test=sentinel.kwarg_test)
        d2 = fetcher(client, self.fake_command, test=sentinel.kwarg_test)

        self.assertIsInstance(d1, Deferred)
        self.assertFalse(d1.called)
        self.assertIsInstance(d2, Deferred)
        self.assertFalse(d2.called)
        self.assertIsNot(d1, d2)

        client.return_value.callback(sentinel.content)
        self.assertIs(extract_result(d1), sentinel.content)
        self.assertIs(extract_result(d2), sentinel.content)

    def test_non_concurrent_gets_do_not_become_related(self):
        client_d1, client_d2 = Deferred(), Deferred()

        client = Mock()
        client.side_effect = [client_d1, client_d2]

        fetcher = RPCFetcher()

        d1 = fetcher(client, self.fake_command, test=sentinel.kwarg_test)
        self.assertIsInstance(d1, Deferred)
        self.assertFalse(d1.called)
        client_d1.callback(sentinel.foo)
        self.assertIs(extract_result(d1), sentinel.foo)

        d2 = fetcher(client, self.fake_command, test=sentinel.kwarg_test)
        self.assertIsInstance(d2, Deferred)
        self.assertFalse(d2.called)
        client_d2.callback(sentinel.bar)
        self.assertIs(extract_result(d2), sentinel.bar)

    def test_errors_are_treated_just_the_same(self):
        client = Mock()
        client.return_value = Deferred()

        fetcher = RPCFetcher()
        d1 = fetcher(client, self.fake_command, test=sentinel.kwarg_test)
        d2 = fetcher(client, self.fake_command, test=sentinel.kwarg_test)

        exception_type = factory.make_exception_type()
        client.return_value.errback(exception_type())

        self.assertRaises(exception_type, extract_result, d1)
        self.assertRaises(exception_type, extract_result, d2)

    def test_clients_are_treated_differently(self):
        client1_d, client2_d = Deferred(), Deferred()

        client1 = Mock()
        client1.return_value = client1_d
        client2 = Mock()
        client2.return_value = client2_d

        fetcher = RPCFetcher()

        d1 = fetcher(client1, self.fake_command, test=sentinel.kwarg_test)
        self.assertIsInstance(d1, Deferred)
        self.assertFalse(d1.called)
        client1_d.callback(sentinel.foo)
        self.assertIs(extract_result(d1), sentinel.foo)

        d2 = fetcher(client2, self.fake_command, test=sentinel.kwarg_test)
        self.assertIsInstance(d2, Deferred)
        self.assertFalse(d2.called)
        client2_d.callback(sentinel.bar)
        self.assertIs(extract_result(d2), sentinel.bar)


class TestDeferToNewThread(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_runs_given_func_in_new_thread(self):
        def thing_to_call(*args, **kwargs):
            thread = threading.current_thread()
            return thread, args, kwargs

        thread, args, kwargs = yield deferToNewThread(
            thing_to_call, sentinel.arg, thing=sentinel.kwarg
        )

        self.assertIsNot(thread, threading.current_thread())
        self.assertEqual(args, (sentinel.arg,))
        self.assertEqual(kwargs, {"thing": sentinel.kwarg})

    @inlineCallbacks
    def test_gives_new_thread_informative_name(self):
        def get_name_of_thread():
            return threading.current_thread().name

        name = yield deferToNewThread(get_name_of_thread)
        self.assertEqual("deferToNewThread(get_name_of_thread)", name)

    @inlineCallbacks
    def test_gives_new_thread_generic_name_if_func_has_no_name(self):
        def get_name_of_thread():
            return threading.current_thread().name

        # Mocks don't have a __name__ property by default.
        func = Mock(side_effect=get_name_of_thread)

        name = yield deferToNewThread(func)
        self.assertEqual("deferToNewThread(...)", name)

    def test_propagates_context_into_thread(self):
        name = factory.make_name("name")
        value = factory.make_name("value")

        def check_context_in_thread():
            self.assertEqual(value, context.get(name))

        return context.call(
            {name: value}, deferToNewThread, check_context_in_thread
        )

    def test_propagates_context_into_callback_from_thread(self):
        name = factory.make_name("name")
        value = factory.make_name("value")

        def do_nothing():
            pass

        def check_context_in_callback(_):
            self.assertEqual(value, context.get(name))

        d = context.call({name: value}, deferToNewThread, do_nothing)
        d.addCallbacks(check_context_in_callback, self.fail)
        return d

    def test_propagates_context_into_errback_from_thread(self):
        name = factory.make_name("name")
        value = factory.make_name("value")

        def break_something():
            0 / 0  # noqa: B018

        def check_context_in_errback(_):
            self.assertEqual(value, context.get(name))

        d = context.call({name: value}, deferToNewThread, break_something)
        d.addCallbacks(self.fail, check_context_in_errback)
        return d


class ThreadUnpoolMixin:
    """Helpers for testing `ThreadUnpool`."""

    def make_semaphore(self, tokens=1):
        lock = DeferredSemaphore(1)

        def assert_empty_waiting():
            self.assertEqual(len(lock.waiting), 0, lock.waiting)

        def assert_tokens_at_limit():
            self.assertEqual(
                lock.tokens,
                lock.limit,
                f"Tokens {lock.tokens} ain't at the limit {lock.limit}",
            )

        self.addCleanup(assert_empty_waiting)
        self.addCleanup(assert_tokens_at_limit)
        return lock


class TestThreadUnpool(MAASTestCase, ThreadUnpoolMixin):
    """Tests for `ThreadUnpool`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_init(self):
        lock = self.make_semaphore()
        unpool = ThreadUnpool(lock)
        self.assertIs(unpool.lock, lock)

    def test_start_sets_started(self):
        unpool = ThreadUnpool(sentinel.lock)
        self.assertIsNone(unpool.started)
        unpool.start()
        self.assertTrue(unpool.started)

    def test_stop_unsets_started(self):
        unpool = ThreadUnpool(sentinel.lock)
        self.assertIsNone(unpool.started)
        unpool.stop()
        self.assertFalse(unpool.started)

    def test_callInThreadWithCallback_makes_callback(self):
        lock = self.make_semaphore()
        unpool = ThreadUnpool(lock)
        callback = Mock()
        d = unpool.callInThreadWithCallback(callback, lambda: sentinel.thing)
        d.addCallback(
            callOut,
            callback.assert_called_once_with,
            True,
            sentinel.thing,
        )
        return d

    def test_callInThreadWithCallback_makes_callback_on_error(self):
        lock = self.make_semaphore()
        unpool = ThreadUnpool(lock)
        callback = Mock()
        failure = Failure(factory.make_exception())
        d = unpool.callInThreadWithCallback(callback, lambda: failure)
        d.addCallback(
            callOut,
            callback.assert_called_once_with,
            False,
            failure,
        )
        return d

    @inlineCallbacks
    def test_callInThreadWithCallback_logs_failure_reporting_result(self):
        unpool = ThreadUnpool(self.make_semaphore())
        onResult = Mock(side_effect=factory.make_exception())
        with TwistedLoggerFixture() as logger:
            yield unpool.callInThreadWithCallback(onResult, return_args)

        self.assertTrue(
            logger.output.startswith(
                "Failure reporting result from thread.\nTraceback (most recent call last):\n"
            ),
            logger.output,
        )

        self.assertIn("maastesting.factory.TestException#", logger.output)


class TestThreadUnpoolCommonBehaviour(MAASTestCase, ThreadUnpoolMixin):
    """Tests for `ThreadUnpool`.

    These test behaviour that's common between `callInThread` and
    `callInThreadWithCallback`.
    """

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    scenarios = (
        (
            "callInThread",
            dict(
                method=lambda unpool, func, *args, **kw: (
                    unpool.callInThread(func, *args, **kw)
                )
            ),
        ),
        (
            "callInThreadWithCallback",
            dict(
                method=lambda unpool, func, *args, **kw: (
                    unpool.callInThreadWithCallback(None, func, *args, **kw)
                )
            ),
        ),
    )

    def test_passes_args_through(self):
        lock = self.make_semaphore()
        unpool = ThreadUnpool(lock)
        func = Mock(__name__="fred")
        func.return_value = None
        d = self.method(unpool, func, sentinel.arg, kwarg=sentinel.kwarg)
        d.addCallback(
            callOut,
            func.assert_called_once_with,
            sentinel.arg,
            kwarg=sentinel.kwarg,
        )
        return d

    def test_defers_to_new_thread(self):
        lock = self.make_semaphore()
        unpool = ThreadUnpool(lock)
        deferToNewThread = self.patch(twisted_module, "deferToNewThread")
        deferToNewThread.return_value = succeed(None)
        d = self.method(unpool, sentinel.func)
        self.assertIsInstance(d, Deferred)
        self.assertTrue(d.called)
        deferToNewThread.assert_called_once_with(sentinel.func)

    @inlineCallbacks
    def test_logs_failure_deferring_to_thread(self):
        lock = self.make_semaphore()
        # Have to manually schedule the lock release, since mocking
        # `deferToNewThread` will prevent the `addBoth` line in
        # callInThreadWithCallback.callInThreadWithLock
        self.addCleanup(lock.release)
        unpool = ThreadUnpool(lock)
        deferToNewThread = self.patch(twisted_module, "deferToNewThread")
        deferToNewThread.side_effect = factory.make_exception()
        with TwistedLoggerFixture() as logger:
            yield self.method(unpool, sentinel.func)

        self.assertTrue(
            logger.output.startswith(
                "Failure when calling out to thread.\nTraceback (most recent call last):"
            )
        )
        self.assertIn("maastesting.factory.TestException#", logger.output)

    @inlineCallbacks
    def test_context_is_active_in_new_thread(self):
        steps = []
        threads = []

        class Context:
            def __enter__(self):
                steps.append("__enter__")
                ct = threading.current_thread()
                threads.append(ct.ident)

            def __exit__(self, *exc_info):
                steps.append("__exit__")
                ct = threading.current_thread()
                threads.append(ct.ident)

        def function():
            steps.append("function")
            ct = threading.current_thread()
            threads.append(ct.ident)

        unpool = ThreadUnpool(self.make_semaphore(), Context)
        yield self.method(unpool, function)

        # The context was active when the function was called.
        self.assertEqual(["__enter__", "function", "__exit__"], steps)
        # All steps happened in the same thread.
        self.assertEqual(len(set(threads)), 1, threads)
        # That thread was not this thread.
        current_thread = threading.current_thread()
        self.assertNotIn(current_thread.ident, threads)


class ContextBrokenOnEntry:
    def __init__(self, exception):
        super().__init__()
        self.exception = exception

    def __enter__(self):
        raise self.exception

    def __exit__(self, *exc_info):
        pass


class ContextBrokenOnExit:
    def __init__(self, exception):
        super().__init__()
        self.exception = exception

    def __enter__(self):
        pass

    def __exit__(self, *exc_info):
        raise self.exception


class TestThreadPool(MAASTestCase):
    """Tests for `ThreadPool`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def assertRaises(self, *args, **kwargs):
        return TestCase.assertRaises(self, *args, **kwargs)

    def test_init(self):
        pool = ThreadPool()
        self.assertEqual(pool.min, 5)
        self.assertEqual(pool.max, 20)
        self.assertIsNone(pool.name)
        self.assertIsInstance(pool.context, twisted_module.ThreadWorkerContext)
        self.assertIs(pool.context.contextFactory, twisted_module.NullContext)

    def test_init_with_parameters(self):
        minthreads = randint(0, 100)
        maxthreads = randint(100, 200)
        pool = ThreadPool(
            minthreads=minthreads,
            maxthreads=maxthreads,
            name=sentinel.name,
            contextFactory=sentinel.contextFactory,
        )
        self.assertEqual(pool.min, minthreads)
        self.assertEqual(pool.max, maxthreads)
        self.assertIs(pool.name, sentinel.name)
        self.assertIsInstance(pool.context, twisted_module.ThreadWorkerContext)
        self.assertIs(pool.context.contextFactory, sentinel.contextFactory)

    @inlineCallbacks
    def test_context_entry_failures_are_propagated_to_tasks(self):
        exception = factory.make_exception()

        pool = ThreadPool(
            contextFactory=partial(ContextBrokenOnEntry, exception),
            minthreads=1,
            maxthreads=1,
        )
        self.addCleanup(stop_pool_if_running, pool)
        pool.start()

        with self.assertRaises(type(exception)):
            yield deferToThreadPool(reactor, pool, lambda: None)

    @inlineCallbacks
    def test_context_exit_failures_are_logged(self):
        exception = factory.make_exception()

        pool = ThreadPool(
            contextFactory=partial(ContextBrokenOnExit, exception),
            minthreads=1,
            maxthreads=1,
        )
        self.addCleanup(stop_pool_if_running, pool)
        pool.start()

        result = yield deferToThreadPool(reactor, pool, lambda: sentinel.foo)
        self.assertIs(result, sentinel.foo)

        with TwistedLoggerFixture() as logger:
            pool.stop()

        self.assertTrue(
            logger.output.startswith(
                "Failure exiting worker context.\nTraceback (most recent call last):"
            )
        )
        self.assertIn("maastesting.factory.TestException#", logger.output)


def stop_pool_if_running(pool):
    """Stop the given thread-pool if it's running."""
    if pool.started:
        pool.stop()


class TestThreadPoolCommonBehaviour(MAASTestCase):
    """Tests for `ThreadPool`.

    These test behaviour that's common between `callInThread` and
    `callInThreadWithCallback`.
    """

    scenarios = (
        (
            "callInThread",
            dict(
                method=lambda pool, func, *args, **kw: (
                    pool.callInThread(func, *args, **kw)
                )
            ),
        ),
        (
            "callInThreadWithCallback",
            dict(
                method=lambda pool, func, *args, **kw: (
                    pool.callInThreadWithCallback(None, func, *args, **kw)
                )
            ),
        ),
    )

    def test_context_is_active_in_new_thread(self):
        steps = []
        threads = []

        class Context:
            def __enter__(self):
                steps.append("__enter__")
                ct = threading.current_thread()
                threads.append(ct.ident)

            def __exit__(self, *exc_info):
                steps.append("__exit__")
                ct = threading.current_thread()
                threads.append(ct.ident)

        def function():
            steps.append("function")
            ct = threading.current_thread()
            threads.append(ct.ident)

        pool = ThreadPool(minthreads=1, maxthreads=1, contextFactory=Context)

        pool.start()
        try:
            self.method(pool, function)
            self.method(pool, function)
        finally:
            pool.stop()

        # The context was active when the function was called both times, and
        # wasn't exited and re-entered in-between.
        self.assertEqual(
            ["__enter__", "function", "function", "__exit__"], steps
        )
        # All steps happened in the same thread.
        self.assertEqual(len(set(threads)), 1)
        # That thread was not this thread.
        current_thread = threading.current_thread()
        self.assertNotIn(current_thread.ident, threads)


class DummyThreadPool:
    start = sentinel.start
    started = sentinel.started
    stop = sentinel.stop


class TestThreadPoolLimiter(MAASTestCase):
    """Tests for `ThreadPoolLimiter`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_init(self):
        pool_beneath = DummyThreadPool()
        pool = ThreadPoolLimiter(pool_beneath, sentinel.lock)
        self.assertIs(pool.pool, pool_beneath)
        self.assertIs(pool.lock, sentinel.lock)
        self.assertIs(pool.start, pool.pool.start)
        self.assertIs(pool.started, pool.pool.started)
        self.assertIs(pool.stop, pool.pool.stop)

    def make_pool(self):
        # Create a pool limited to one thread, with an underlying pool that
        # allows a greater number of concurrent threads so it won't interfere
        # with the test.
        pool_beneath = ThreadUnpool(DeferredSemaphore(2))
        pool = ThreadPoolLimiter(pool_beneath, DeferredSemaphore(1))
        return pool

    def test_callInThread_calls_callInThreadWithCallback(self):
        pool = self.make_pool()
        self.patch_autospec(pool, "callInThreadWithCallback")
        pool.callInThreadWithCallback.return_value = sentinel.called
        pool.callInThread(sentinel.func, sentinel.arg, kwarg=sentinel.kwarg)
        pool.callInThreadWithCallback.assert_called_once_with(
            None, sentinel.func, sentinel.arg, kwarg=sentinel.kwarg
        )

    @inlineCallbacks
    def test_without_callback_acquires_and_releases_lock(self):
        pool = self.make_pool()  # Limit to a single thread.
        # Callback from a thread.
        d = Deferred()

        def function():
            reactor.callFromThread(d.callback, sentinel.done)
            return sentinel.result

        pool.callInThreadWithCallback(None, function)
        self.assertIs((yield d), sentinel.done)
        # The lock has not yet been released.
        self.assertEqual(0, pool.lock.tokens)
        # Wait and it shall be released.
        yield pool.lock.run(noop)
        self.assertEqual(1, pool.lock.tokens)

    @inlineCallbacks
    def test_with_callback_acquires_and_releases_lock(self):
        pool = self.make_pool()  # Limit to a single thread.
        # Callback from a thread.
        d, callback = Deferred(), Mock()

        def function():
            reactor.callFromThread(d.callback, sentinel.done)
            return sentinel.result

        pool.callInThreadWithCallback(callback, function)
        self.assertIs((yield d), sentinel.done)
        # The lock has not yet been released.
        self.assertEqual(0, pool.lock.tokens)
        # Wait and it shall be released.
        yield pool.lock.run(noop)
        self.assertEqual(1, pool.lock.tokens)
        # The callback has also been called.
        callback.assert_called_once_with(True, sentinel.result)

    @inlineCallbacks
    def test_without_callback_releases_lock_when_underlying_pool_breaks(self):
        pool = self.make_pool()  # Limit to a single thread.

        exception_type = factory.make_exception_type()
        citwc = self.patch_autospec(pool.pool, "callInThreadWithCallback")
        citwc.side_effect = exception_type

        with TwistedLoggerFixture() as logger:
            yield pool.callInThreadWithCallback(None, noop)

        # Wait and it shall be released.
        yield pool.lock.run(noop)
        self.assertEqual(1, pool.lock.tokens)

        # An alarming message is logged.
        self.assertTrue(
            logger.output.startswith(
                "Critical failure arranging call in thread\nTraceback (most recent call last):"
            )
        )
        self.assertIn("maastesting.factory.TestException#", logger.output)

    @inlineCallbacks
    def test_with_callback_releases_lock_when_underlying_pool_breaks(self):
        pool = self.make_pool()  # Limit to a single thread.

        exception_type = factory.make_exception_type()
        citwc = self.patch_autospec(pool.pool, "callInThreadWithCallback")
        citwc.side_effect = exception_type

        callback = Mock()
        with TwistedLoggerFixture() as logger:
            yield pool.callInThreadWithCallback(callback, noop)

        # Wait and it shall be released.
        yield pool.lock.run(noop)
        self.assertEqual(1, pool.lock.tokens)

        # Nothing is logged...
        self.assertEqual("", logger.output)
        # ... but the callback has been called.
        callback.assert_called_once_with(False, ANY)
        [success, result] = callback.call_args[0]
        self.assertIsInstance(result, Failure)
        self.assertIsInstance(result.value, exception_type)

    @inlineCallbacks
    def test_when_deferring_acquires_and_releases_lock(self):
        pool = self.make_pool()
        # Within the thread the lock had been acquired.
        tokens_in_thread = yield deferToThreadPool(
            reactor, pool, lambda: pool.lock.tokens
        )
        self.assertEqual(0, tokens_in_thread)
        # The lock has not yet been released.
        self.assertEqual(0, pool.lock.tokens)
        # Wait and it shall be released.
        yield pool.lock.run(noop)
        self.assertEqual(1, pool.lock.tokens)

    @inlineCallbacks
    def test_when_deferring_acquires_and_releases_lock_on_error(self):
        pool = self.make_pool()
        # Within the thread the lock had been acquired.
        with TestCase.assertRaises(self, ZeroDivisionError):
            yield deferToThreadPool(reactor, pool, lambda: 0 / 0)
        # The lock has not yet been released.
        self.assertEqual(0, pool.lock.tokens)
        # Wait and it shall be released.
        yield pool.lock.run(noop)
        self.assertEqual(1, pool.lock.tokens)


class TestMakeDeferredWithProcessProtocol(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_calls_callback_when_processended_called_with_none(self):
        d, protocol = makeDeferredWithProcessProtocol()
        protocol.processEnded(None)
        result = yield d
        self.assertIsNone(result)

    @inlineCallbacks
    def test_calls_callback_when_process_called_with_processdone(self):
        d, protocol = makeDeferredWithProcessProtocol()
        protocol.processEnded(Failure(ProcessDone(0)))
        result = yield d
        self.assertIsNone(result)

    @inlineCallbacks
    def test_calls_errback_when_processEnded_called_with_failure(self):
        d, protocol = makeDeferredWithProcessProtocol()
        exception = factory.make_exception()
        protocol.processEnded(Failure(exception))
        with TestCase.assertRaises(self, type(exception)):
            yield d


# A script that prints the signals it receives, as long as they're SIGTERM or
# SIGQUIT. It prints "Ready." on stderr once it's registered signal handlers.

# This sets itself as process group leader.
signal_printer_pgl = """\
from os import setpgrp
from signal import Signals, signal
from sys import stderr
from time import sleep
from traceback import print_exc

def print_signal(signum, frame):
    print(Signals(signum).name, flush=True)

signal(Signals.SIGTERM, print_signal)
signal(Signals.SIGQUIT, print_signal)

setpgrp()

print("Ready.", file=stderr, flush=True)

sleep(5.0)
"""

# This variant should be identical, except that it does
# not set itself as process group leader.
signal_printer = """\
from signal import Signals, signal
from sys import stderr
from time import sleep
from traceback import print_exc

def print_signal(signum, frame):
    print(Signals(signum).name, flush=True)

signal(Signals.SIGTERM, print_signal)
signal(Signals.SIGQUIT, print_signal)

print("Ready.", file=stderr, flush=True)

sleep(5.0)
"""


class SignalPrinterProtocol(ProcessProtocol):
    """Process protocol for use with `signal_printer`."""

    def __init__(self):
        super().__init__()
        self.ready = Deferred()
        self.done = Deferred()
        self.out = io.BytesIO()
        self.err = io.BytesIO()

    def outReceived(self, data):
        self.out.write(data)

    def errReceived(self, data):
        self.err.write(data)
        if not self.ready.called:
            self.ready.callback(data)

    def processEnded(self, reason):
        self.done.callback(reason)


class TestTerminateProcess(MAASTestCase):
    """Tests for `terminateProcess`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        # Allow spying on calls to os.kill and os.killpg by terminateProcess.
        self.assertIs(twisted_module._os_kill, os.kill)
        self.patch(
            twisted_module, "_os_kill", Mock(wraps=twisted_module._os_kill)
        )
        self.assertIs(twisted_module._os_killpg, os.killpg)
        self.patch(
            twisted_module, "_os_killpg", Mock(wraps=twisted_module._os_killpg)
        )

    def startSignalPrinter(self, protocol, *, pgrp=False):
        script_filename = self.make_file(
            "sigprint.py", signal_printer_pgl if pgrp else signal_printer
        )

        self.assertIsInstance(protocol, SignalPrinterProtocol)
        self.addDetail("out", content_from_stream(protocol.out, seek_offset=0))
        self.addDetail("err", content_from_stream(protocol.err, seek_offset=0))
        python = sys.executable.encode("utf-8")
        process = reactor.spawnProcess(
            protocol, python, (python, script_filename.encode("utf-8"))
        )

        # Wait for the spawned subprocess to tell us that it's ready.
        def cbReady(message):
            self.assertEqual("Ready.\n", message.decode("utf-8"))
            return process

        return protocol.ready.addCallback(cbReady)

    def terminateSignalPrinter(self, process, protocol):
        # Terminate with some short timings; no point waiting long in a test,
        # and we need to do it before the subprocess finishes sleeping.
        terminateProcess(
            process.pid, protocol.done, quit_after=0.1, kill_after=0.2
        )

    @inlineCallbacks
    def test_terminates_process_with_TERM_QUIT_then_KILL(self):
        protocol = SignalPrinterProtocol()
        process = yield self.startSignalPrinter(protocol)
        self.terminateSignalPrinter(process, protocol)
        # The subprocess is terminated with SIGKILL but received SIGTERM then
        # SIGQUIT prior to that.
        try:
            yield protocol.done
        except ProcessTerminated as reason:
            self.assertIsInstance(reason, ProcessTerminated)
            self.assertEqual(signal.SIGKILL, reason.signal)
            self.assertEqual(
                ["SIGTERM", "SIGQUIT"],
                protocol.out.getvalue().decode("utf-8").split(),
            )

    @inlineCallbacks
    def test_terminates_with_kill_and_killpg(self):
        protocol = SignalPrinterProtocol()
        process = yield self.startSignalPrinter(protocol, pgrp=True)
        # Capture the pid now; it gets cleared when the process exits.
        pid = process.pid
        # Terminate and wait for it to exit.
        self.terminateSignalPrinter(process, protocol)
        yield protocol.done.addErrback(suppress, ProcessTerminated)
        # os.kill was called once then os.killpg was called twice because the
        # subprocess made itself a process group leader.
        twisted_module._os_kill.assert_called_once_with(pid, signal.SIGTERM)
        twisted_module._os_killpg.assert_has_calls(
            [mock.call(pid, signal.SIGQUIT), mock.call(pid, signal.SIGKILL)]
        )

    @inlineCallbacks
    def test_terminates_with_kill_if_not_in_separate_process_group(self):
        protocol = SignalPrinterProtocol()
        process = yield self.startSignalPrinter(protocol, pgrp=False)
        # Capture the pid now; it gets cleared when the process exits.
        pid = process.pid
        # Terminate and wait for it to exit.
        self.terminateSignalPrinter(process, protocol)
        yield protocol.done.addErrback(suppress, ProcessTerminated)
        # os.kill was called 3 times because the subprocess did not make
        # itself a process group leader.
        twisted_module._os_kill.assert_has_calls(
            [
                mock.call(pid, signal.SIGTERM),
                mock.call(pid, signal.SIGQUIT),
                mock.call(pid, signal.SIGKILL),
            ]
        )
        twisted_module._os_killpg.assert_not_called()


class TestReducedWebLogFormatter(MAASTestCase):
    """Tests for `reducedWebLogFormatter`."""

    ipv4_address = factory.make_ipv4_address()
    ipv6_address = factory.make_ipv6_address()
    simple_http_url = factory.make_simple_http_url()
    simple_uri = factory.make_absolute_path()
    agent_name = factory.make_name("agent")
    status = factory.make_status_code()

    scenarios_methods = (
        ("no-method", {"method": None, "method_expected": "???"}),
        ("method", {"method": "GET", "method_expected": "GET"}),
    )

    scenarios_clients = (
        ("no-client", {"client": None, "client_expected": "-"}),
        (
            "ipv4-client",
            {"client": ipv4_address, "client_expected": ipv4_address},
        ),
        (
            "ipv6-client",
            {"client": ipv6_address, "client_expected": ipv6_address},
        ),
        (
            "ipv4-mapped-client",
            {
                "client": "::ffff:" + ipv4_address,
                "client_expected": ipv4_address,
            },
        ),
    )

    scenarios_referrers = (
        ("no-referrer", {"referrer": None, "referrer_expected": "-"}),
        (
            "referrer",
            {
                "referrer": simple_http_url,
                "referrer_expected": simple_http_url,
            },
        ),
    )

    scenarios_agents = (
        ("no-agent", {"agent": None, "agent_expected": "-"}),
        ("agent", {"agent": agent_name, "agent_expected": agent_name}),
    )

    scenarios_uris = (
        ("no-uri", {"uri": None, "uri_expected": "-"}),
        ("uri", {"uri": simple_uri, "uri_expected": simple_uri}),
    )

    scenarios_statuses = (
        ("no-status", {"status": None, "status_expected": "???"}),
        (
            "status",
            {
                "status": status.value,
                "status_expected": "%d %s" % (status.value, status.name),
            },
        ),
        ("status-unknown", {"status": 678, "status_expected": "678"}),
    )

    scenarios_types = (
        ("plain", {"prep": lambda string: string}),
        (
            "bytes",
            {
                "prep": lambda string: (
                    None if string is None else string.encode("ascii")
                )
            },
        ),
    )

    scenarios = multiply_scenarios(
        scenarios_methods,
        scenarios_clients,
        scenarios_referrers,
        scenarios_agents,
        scenarios_uris,
        scenarios_statuses,
        scenarios_types,
    )

    def test_renders_full_request(self):
        request = requesthelper.DummyRequest("foo/bar")
        request.method = self.prep(self.method)
        request.client = address.IPv4Address(
            "TCP", self.prep(self.client), 12345
        )
        referer = self.prep(self.referrer)
        if referer is not None:
            request.requestHeaders.addRawHeader("referer", referer)
        user_agent = self.prep(self.agent)
        if user_agent is not None:
            request.requestHeaders.addRawHeader("user-agent", user_agent)
        request.uri = self.prep(self.uri)
        request.code = self.status

        self.assertEqual(
            reducedWebLogFormatter(sentinel.timestamp, request),
            "%s %s %s HTTP/1.0 --> %s (referrer: %s; agent: %s)"
            % (
                self.client_expected,
                self.method_expected,
                self.uri_expected,
                self.status_expected,
                self.referrer_expected,
                self.agent_expected,
            ),
        )
