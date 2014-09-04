# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.timers`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import (
    datetime,
    timedelta,
    )

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from mock import Mock
from provisioningserver.rpc import timers as timers_module
from provisioningserver.rpc.region import TimerExpired
from provisioningserver.rpc.timers import (
    cancel_timer,
    running_timers,
    start_timers,
    )
from provisioningserver.testing.testcase import PservTestCase
from testtools.matchers import (
    Contains,
    Equals,
    HasLength,
    IsInstance,
    Not,
    )
from twisted.internet.base import DelayedCall
from twisted.internet.task import Clock
from twisted.protocols import amp


def make_timers(time_now=None):
    """Make some StartTimers, set to go off one second apart starting in
    one second"""
    if time_now is None:
        time_now = datetime.now(amp.utc)
    timers = []
    for i in xrange(2):
        timers.append({
            "deadline": time_now + timedelta(seconds=i + 1),
            "context": factory.make_name("context"),
            "id": factory.make_name("id"),
            })
    return timers


class TestStartTimers(PservTestCase):
    """Tests for `~provisioningserver.rpc.timers.start_timers`."""

    def test__sets_up_running_timers(self):
        clock = Clock()
        timers = make_timers()
        start_timers(timers, clock)

        self.expectThat(running_timers, HasLength(len(timers)))
        for timer in timers:
            id = timer["id"]
            self.expectThat(running_timers[id], IsInstance(tuple))
            delayed_call, context = running_timers[id]
            self.expectThat(delayed_call, IsInstance(DelayedCall))
            self.expectThat(context, Equals(timer["context"]))

    def test__removes_from_running_timers_when_timer_expires(self):
        self.patch(timers_module, "getRegionClient")
        clock = Clock()
        timers = make_timers()
        start_timers(timers, clock)

        # Expire the first timer.
        clock.advance(1)
        self.assertThat(running_timers, Not(Contains(timers[0]["id"])))
        self.assertThat(running_timers, Contains(timers[1]["id"]))

        # Expire the other time.
        clock.advance(1)
        self.assertThat(running_timers, Not(Contains(timers[1]["id"])))

    def test__calls_TimerExpired_when_timer_expires(self):
        getRegionClient = self.patch(timers_module, "getRegionClient")
        client = Mock()
        getRegionClient.return_value = client
        clock = Clock()
        timers = make_timers()
        # Just use the first one for this test.
        timer = timers[0]
        start_timers([timer], clock)
        clock.advance(1)

        self.assertThat(
            client,
            MockCalledOnceWith(
                TimerExpired, id=timer["id"],
                context=timer["context"]))


class TestCancelTimer(PservTestCase):
    """Tests for `~provisioningserver.rpc.timers.cancel_timer`."""

    def test__cancels_running_timer(self):
        timers = make_timers()
        clock = Clock()
        start_timers(timers, clock)
        dc, _ = running_timers[timers[0]["id"]]

        cancel_timer(timers[0]["id"])

        self.expectThat(running_timers, Not(Contains(timers[0]["id"])))
        self.expectThat(running_timers, Contains(timers[1]["id"]))
        self.assertTrue(dc.cancelled)

    def test__silently_ignores_already_cancelled_timer(self):
        timers = make_timers()
        clock = Clock()
        self.addCleanup(running_timers.clear)
        start_timers(timers, clock)

        cancel_timer(factory.make_string())

        self.expectThat(running_timers, Contains(timers[0]["id"]))
        self.expectThat(running_timers, Contains(timers[1]["id"]))
