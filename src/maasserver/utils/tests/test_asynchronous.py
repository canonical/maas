# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for asynchronous utilities."""

import asyncio
from functools import partial
import threading
from time import time
from unittest.mock import call, Mock, sentinel

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.task import deferLater
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread

from maasserver.exceptions import IteratorReusedError
from maasserver.testing.orm import PostCommitHooksTestMixin
from maasserver.utils import asynchronous
from maasserver.utils.asynchronous import async_retry, DeferredHooks
from maastesting.crochet import wait_for
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result, TwistedLoggerFixture


class TestGather(MAASTestCase):
    def test_gather_nothing(self):
        time_before = time()
        results = list(asynchronous.gather([], timeout=10))
        time_after = time()
        self.assertEqual([], results)
        # gather() should return well within 9 seconds; this shows
        # that the call is not timing out.
        self.assertLess(time_after - time_before, 9)


class TestGatherScenarios(MAASTestCase):
    scenarios = (
        (
            "synchronous",
            {
                # Return the call as-is.
                "wrap": lambda call: call
            },
        ),
        (
            "asynchronous",
            {
                # Defer the call to a later reactor iteration.
                "wrap": lambda call: partial(deferLater, reactor, 0, call)
            },
        ),
    )

    def test_gather_from_calls_without_errors(self):
        values = [self.getUniqueInteger(), self.getUniqueString()]
        calls = [self.wrap(lambda v=value: v) for value in values]
        results = list(asynchronous.gather(calls))
        self.assertCountEqual(values, results)

    def test_gatherCallResults_returns_use_once_iterator(self):
        calls = []
        results = asynchronous.gatherCallResults(calls)
        self.assertIsInstance(results, asynchronous.UseOnceIterator)

    def test_gather_from_calls_with_errors(self):
        calls = [(lambda: sentinel.okay), (lambda: 1 / 0)]  # ZeroDivisionError
        calls = [self.wrap(call) for call in calls]
        results = list(asynchronous.gather(calls))

        self.assertIn(sentinel.okay, results)
        results.remove(sentinel.okay)
        self.assertEqual(len(results), 1)
        failure = results[0]
        self.assertIsInstance(failure, Failure)
        self.assertIs(failure.type, ZeroDivisionError)

    def test_gatherCallResults_yields_call_result_tuples(self):
        values = [self.getUniqueInteger(), self.getUniqueString()]
        calls = [self.wrap(lambda v=value: v) for value in values]
        results = list(asynchronous.gatherCallResults(calls))
        expected_results = [(calls[0], values[0]), (calls[1], values[1])]
        self.assertCountEqual(expected_results, results)


class TestUseOnceIterator(MAASTestCase):
    def test_returns_correct_items_for_list(self):
        expected_values = list(range(10))
        iterator = asynchronous.UseOnceIterator(expected_values)
        actual_values = [val for val in iterator]
        self.assertEqual(expected_values, actual_values)

    def test_raises_stop_iteration(self):
        iterator = asynchronous.UseOnceIterator([])
        self.assertRaises(StopIteration, iterator.__next__)

    def test_raises_iterator_reused(self):
        iterator = asynchronous.UseOnceIterator([])
        # Loop over the iterator to get to the point where we might try
        # and reuse it.
        list(iterator)
        self.assertRaises(IteratorReusedError, iterator.__next__)


class TestDeferredHooks(MAASTestCase, PostCommitHooksTestMixin):
    def test_is_thread_local(self):
        dhooks = DeferredHooks()
        queues = []
        for _ in range(3):
            thread = threading.Thread(
                target=lambda: queues.append(dhooks.hooks)
            )
            thread.start()
            thread.join()
        self.assertEqual(len(queues), 3)
        # Each queue is distinct (deque is unhashable; use the id() of each).
        self.assertEqual(len({id(q) for q in queues}), 3)

    def test_add_appends_Deferred_to_queue(self):
        dhooks = DeferredHooks()
        self.assertEqual(len(dhooks.hooks), 0)
        dhooks.add(Deferred())
        self.assertEqual(len(dhooks.hooks), 1)

    def test_add_cannot_be_called_in_the_reactor(self):
        dhooks = DeferredHooks()
        add_in_reactor = wait_for()(dhooks.add)  # Wait 30 seconds.
        self.assertRaises(AssertionError, add_in_reactor, Deferred())

    def test_fire_calls_hooks(self):
        dhooks = DeferredHooks()
        ds = Deferred(), Deferred()
        for d in ds:
            dhooks.add(d)
        dhooks.fire()
        for d in ds:
            self.assertIsNone(extract_result(d))

    def test_fire_calls_hooks_in_reactor(self):
        def validate_in_reactor(_):
            self.assertTrue(isInIOThread())

        dhooks = DeferredHooks()
        d = Deferred()
        d.addCallback(validate_in_reactor)
        dhooks.add(d)
        dhooks.fire()
        self.assertTrue(d.called)

    def test_fire_propagates_error_from_hook(self):
        error = factory.make_exception()
        dhooks = DeferredHooks()
        d = Deferred()
        d.addCallback(lambda _: Failure(error))
        dhooks.add(d)
        self.assertRaises(type(error), dhooks.fire)

    def test_fire_always_consumes_all_hooks(self):
        dhooks = DeferredHooks()
        d1, d2 = Deferred(), Deferred()
        d1.addCallback(lambda _: 0 / 0)  # d1 will fail.
        dhooks.add(d1)
        dhooks.add(d2)
        self.assertRaises(ZeroDivisionError, dhooks.fire)
        self.assertEqual(len(dhooks.hooks), 0)
        self.assertTrue(d1.called)
        self.assertTrue(d2.called)

    def test_reset_cancels_all_hooks(self):
        canceller = Mock()
        dhooks = DeferredHooks()
        d1, d2 = Deferred(canceller), Deferred(canceller)
        dhooks.add(d1)
        dhooks.add(d2)
        dhooks.reset()
        self.assertEqual(len(dhooks.hooks), 0)
        canceller.assert_has_calls((call(d1), call(d2)))

    def test_reset_cancels_in_reactor(self):
        def validate_in_reactor(_):
            self.assertTrue(isInIOThread())

        dhooks = DeferredHooks()
        d = Deferred()
        d.addBoth(validate_in_reactor)
        dhooks.add(d)
        dhooks.reset()
        self.assertEqual(len(dhooks.hooks), 0)
        self.assertTrue(d.called)

    def test_reset_suppresses_CancelledError(self):
        logger = self.useFixture(TwistedLoggerFixture())

        dhooks = DeferredHooks()
        d = Deferred()
        dhooks.add(d)
        dhooks.reset()
        self.assertEqual(len(dhooks.hooks), 0)
        self.assertIsNone(extract_result(d))
        self.assertEqual("", logger.output)

    def test_logs_failures_from_cancellers(self):
        logger = self.useFixture(TwistedLoggerFixture())

        canceller = Mock()
        canceller.side_effect = factory.make_exception()

        dhooks = DeferredHooks()
        d = Deferred(canceller)
        dhooks.add(d)
        dhooks.reset()
        self.assertEqual(len(dhooks.hooks), 0)
        # The hook has not been fired, but because the user-supplied canceller
        # has failed we're not in a position to know what to do. This reflects
        # a programming error and not a run-time error that we ought to be
        # prepared for, so it is left as-is.
        self.assertFalse(d.called)
        self.assertIn("Failure when cancelling hook.", logger.output)

    def test_logs_failures_from_cancellers_when_hook_already_fired(self):
        logger = self.useFixture(TwistedLoggerFixture())

        def canceller(d):
            d.callback(None)
            raise factory.make_exception()

        dhooks = DeferredHooks()
        d = Deferred(canceller)
        dhooks.add(d)
        dhooks.reset()
        self.assertEqual(len(dhooks.hooks), 0)
        self.assertTrue(d.called)
        self.assertIn("Failure when cancelling hook.", logger.output)

    def test_logs_failures_from_cancelled_hooks(self):
        logger = self.useFixture(TwistedLoggerFixture())

        error = factory.make_exception()
        dhooks = DeferredHooks()
        d = Deferred()
        d.addBoth(lambda _: Failure(error))
        dhooks.add(d)
        dhooks.reset()
        self.assertEqual(len(dhooks.hooks), 0)
        self.assertTrue(d.called)
        self.assertIn("Failure when cancelling hook.", logger.output)

    def test_savepoint_saves_and_restores_hooks(self):
        d = Deferred()
        dhooks = DeferredHooks()
        dhooks.add(d)

        with dhooks.savepoint():
            self.assertEqual(list(dhooks.hooks), [])

        self.assertEqual(list(dhooks.hooks), [d])

    def test_savepoint_restores_hooks_with_new_hooks_on_clean_exit(self):
        d1 = Deferred()
        d2 = Deferred()
        dhooks = DeferredHooks()
        dhooks.add(d1)

        with dhooks.savepoint():
            dhooks.add(d2)
            self.assertEqual(list(dhooks.hooks), [d2])

        self.assertEqual(list(dhooks.hooks), [d1, d2])

    def test_savepoint_restores_hooks_only_on_dirty_exit(self):
        d1 = Deferred()
        d2 = Deferred()
        dhooks = DeferredHooks()
        dhooks.add(d1)

        exception_type = factory.make_exception_type()
        with self.assertRaisesRegex(exception_type, ""):
            with dhooks.savepoint():
                dhooks.add(d2)
                raise exception_type()

        self.assertEqual(list(dhooks.hooks), [d1])


class TestAsyncRetry(MAASTestCase):
    def test_async_retry_retries_async_function(self):
        mock = Mock()

        @async_retry(retries=2, backoff_ms=1)
        async def _fn():
            mock.fn()
            raise Exception()

        try:
            asyncio.run(_fn())
        except Exception:
            pass

        mock.fn.assert_called()
        self.assertEqual(mock.fn.call_count, 2)

    def test_async_retry_does_not_retry_success(self):
        mock = Mock()

        @async_retry(retries=2, backoff_ms=1)
        async def _fn():
            mock.fn()

        asyncio.run(_fn())

        mock.fn.assert_called()
        self.assertEqual(mock.fn.call_count, 1)
