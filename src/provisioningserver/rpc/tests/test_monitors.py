# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.monitors`."""

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
from provisioningserver.rpc import monitors as monitors_module
from provisioningserver.rpc.monitors import (
    cancel_monitor,
    running_monitors,
    start_monitors,
    )
from provisioningserver.rpc.region import MonitorExpired
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


def make_monitors(time_now=None):
    """Make some StartMonitors, set to go off one second apart starting in
    one second"""
    if time_now is None:
        time_now = datetime.now(amp.utc)
    monitors = []
    for i in xrange(2):
        monitors.append({
            "deadline": time_now + timedelta(seconds=i + 1),
            "context": factory.make_name("context"),
            "id": factory.make_name("id"),
            })
    return monitors


class TestStartMonitors(PservTestCase):
    """Tests for `~provisioningserver.rpc.monitors.start_monitors`."""

    def test__sets_up_running_monitors(self):
        clock = Clock()
        monitors = make_monitors()
        start_monitors(monitors, clock)

        self.expectThat(running_monitors, HasLength(len(monitors)))
        for monitor in monitors:
            id = monitor["id"]
            self.expectThat(running_monitors[id], IsInstance(tuple))
            delayed_call, context = running_monitors[id]
            self.expectThat(delayed_call, IsInstance(DelayedCall))
            self.expectThat(context, Equals(monitor["context"]))

    def test__removes_from_running_monitors_when_monitor_expires(self):
        self.patch(monitors_module, "getRegionClient")
        clock = Clock()
        monitors = make_monitors()
        start_monitors(monitors, clock)

        # Expire the first monitor.
        clock.advance(1)
        self.assertThat(running_monitors, Not(Contains(monitors[0]["id"])))
        self.assertThat(running_monitors, Contains(monitors[1]["id"]))

        # Expire the other time.
        clock.advance(1)
        self.assertThat(running_monitors, Not(Contains(monitors[1]["id"])))

    def test__calls_MonitorExpired_when_monitor_expires(self):
        getRegionClient = self.patch(monitors_module, "getRegionClient")
        client = Mock()
        getRegionClient.return_value = client
        clock = Clock()
        monitors = make_monitors()
        # Just use the first one for this test.
        monitor = monitors[0]
        start_monitors([monitor], clock)
        clock.advance(1)

        self.assertThat(
            client,
            MockCalledOnceWith(
                MonitorExpired, id=monitor["id"],
                context=monitor["context"]))


class TestCancelMonitor(PservTestCase):
    """Tests for `~provisioningserver.rpc.monitors.cancel_monitor`."""

    def test__cancels_running_monitor(self):
        monitors = make_monitors()
        clock = Clock()
        start_monitors(monitors, clock)
        dc, _ = running_monitors[monitors[0]["id"]]

        cancel_monitor(monitors[0]["id"])

        self.expectThat(running_monitors, Not(Contains(monitors[0]["id"])))
        self.expectThat(running_monitors, Contains(monitors[1]["id"]))
        self.assertTrue(dc.cancelled)

    def test__silently_ignores_already_cancelled_monitor(self):
        monitors = make_monitors()
        clock = Clock()
        self.addCleanup(running_monitors.clear)
        start_monitors(monitors, clock)

        cancel_monitor(factory.make_string())

        self.expectThat(running_monitors, Contains(monitors[0]["id"]))
        self.expectThat(running_monitors, Contains(monitors[1]["id"]))
