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
from maasserver.utils import async
from maastesting.testcase import MAASTestCase
from mock import sentinel
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
