# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for asynchronous utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from functools import partial
from time import time

import crochet
from django.db import connection
from maasserver.exceptions import IteratorReusedError
from maasserver.utils import async
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    Is,
    IsInstance,
    LessThan,
    )
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.python.failure import Failure

# These tests need a running reactor.
crochet.setup()


class TestGather(MAASTestCase):

    def test_gather_nothing(self):
        time_before = time()
        results = list(async.gather([], timeout=10))
        time_after = time()
        self.assertThat(results, Equals([]))
        # gather() should return well within 9 seconds; this shows
        # that the call is not timing out.
        self.assertThat(time_after - time_before, LessThan(9))


class TestGatherScenarios(MAASTestCase):

    scenarios = (
        ("synchronous", {
            # Return the call as-is.
            "wrap": lambda call: call,
        }),
        ("asynchronous", {
            # Defer the call to a later reactor iteration.
            "wrap": lambda call: partial(deferLater, reactor, 0, call),
        }),
    )

    def test_gather_from_calls_without_errors(self):
        values = [
            self.getUniqueInteger(),
            self.getUniqueString(),
        ]
        calls = [
            self.wrap(lambda v=value: v)
            for value in values
        ]
        results = list(async.gather(calls))

        self.assertItemsEqual(values, results)

    def test_returns_use_once_iterator(self):
        calls = []
        results = async.gather(calls)
        self.assertIsInstance(results, async.UseOnceIterator)

    def test_gather_from_calls_with_errors(self):
        calls = [
            (lambda: sentinel.okay),
            (lambda: 1 / 0),  # ZeroDivisionError
        ]
        calls = [self.wrap(call) for call in calls]
        results = list(async.gather(calls))

        self.assertThat(results, Contains(sentinel.okay))
        results.remove(sentinel.okay)
        self.assertThat(results, HasLength(1))
        failure = results[0]
        self.assertThat(failure, IsInstance(Failure))
        self.assertThat(failure.type, Is(ZeroDivisionError))


class TestUseOnceIterator(MAASTestCase):

    def test_returns_correct_items_for_list(self):
        expected_values = [i for i in range(10)]
        iterator = async.UseOnceIterator(expected_values)
        actual_values = [val for val in iterator]
        self.assertEqual(expected_values, actual_values)

    def test_raises_stop_iteration(self):
        iterator = async.UseOnceIterator([])
        self.assertRaises(StopIteration, iterator.next)

    def test_raises_iterator_reused(self):
        iterator = async.UseOnceIterator([])
        # Loop over the iterator to get to the point where we might try
        # and reuse it.
        [i for i in iterator]
        self.assertRaises(IteratorReusedError, iterator.next)


class TestTransactional(MAASTestCase):

    def test_calls_function_within_transaction_then_closes_connections(self):
        close_old_connections = self.patch(async, "close_old_connections")

        # No transaction has been entered (what Django calls an atomic
        # block), and old connections have not been closed.
        self.assertFalse(connection.in_atomic_block)
        self.assertThat(close_old_connections, MockNotCalled())

        def check_inner(*args, **kwargs):
            # In here, the transaction (`atomic`) has been started but
            # is not over, and old connections have not yet been closed.
            self.assertTrue(connection.in_atomic_block)
            self.assertThat(close_old_connections, MockNotCalled())

        function = Mock()
        function.__name__ = self.getUniqueString()
        function.side_effect = check_inner

        # Call `function` via the `transactional` decorator.
        decorated_function = async.transactional(function)
        decorated_function(sentinel.arg, kwarg=sentinel.kwarg)

        # `function` was called -- and therefore `check_inner` too --
        # and the arguments passed correctly.
        self.assertThat(function, MockCalledOnceWith(
            sentinel.arg, kwarg=sentinel.kwarg))

        # After the decorated function has returned the transaction has
        # been exited, and old connections have been closed.
        self.assertFalse(connection.in_atomic_block)
        self.assertThat(close_old_connections, MockCalledOnceWith())
