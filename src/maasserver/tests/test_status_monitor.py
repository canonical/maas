# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the status monitor module."""

__all__ = []


from datetime import (
    datetime,
    timedelta,
)
from unittest.mock import call

from maasserver import status_monitor
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.node_status import NODE_FAILURE_STATUS_TRANSITIONS
from maasserver.status_monitor import (
    mark_nodes_failed_after_expiring,
    StatusMonitorService,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from twisted.internet.defer import maybeDeferred
from twisted.internet.task import Clock


class TestMarkNodesFailedAfterExpiring(MAASServerTestCase):

    def test__marks_all_possible_failed_status_as_failed(self):
        self.useFixture(SignalsDisabled("power"))
        current_time = datetime.now()
        self.patch(status_monitor, "now").return_value = current_time
        expired_time = current_time - timedelta(minutes=1)
        nodes = [
            factory.make_Node(status=status, status_expires=expired_time)
            for status in NODE_FAILURE_STATUS_TRANSITIONS.keys()
        ]
        mark_nodes_failed_after_expiring()
        failed_statuses = [
            reload_object(node).status
            for node in nodes
        ]
        self.assertItemsEqual(
            NODE_FAILURE_STATUS_TRANSITIONS.values(), failed_statuses)

    def test__skips_those_that_have_not_expired(self):
        self.useFixture(SignalsDisabled("power"))
        current_time = datetime.now()
        self.patch(status_monitor, "now").return_value = current_time
        expired_time = current_time + timedelta(minutes=1)
        nodes = [
            factory.make_Node(status=status, status_expires=expired_time)
            for status in NODE_FAILURE_STATUS_TRANSITIONS.keys()
        ]
        mark_nodes_failed_after_expiring()
        failed_statuses = [
            reload_object(node).status
            for node in nodes
        ]
        self.assertItemsEqual(
            NODE_FAILURE_STATUS_TRANSITIONS.keys(), failed_statuses)


class TestStatusMonitorService(MAASServerTestCase):

    def test_init_with_default_interval(self):
        # The service itself calls `mark_nodes_failed_after_expiring` in a
        # thread, via a couple of decorators. This indirection makes it
        # clearer to mock `cleanup_old_nonces` here and track calls to it.
        mark_nodes_failed_after_expiring = self.patch(
            status_monitor, "mark_nodes_failed_after_expiring")
        # Making `deferToDatabase` use the current thread helps testing.
        self.patch(status_monitor, "deferToDatabase", maybeDeferred)

        service = StatusMonitorService()
        # Use a deterministic clock instead of the reactor for testing.
        service.clock = Clock()

        # The interval is stored as `step` by TimerService,
        # StatusMonitorService's parent class.
        interval = 2 * 60  # seconds.
        self.assertEqual(service.step, interval)

        # `mark_nodes_failed_after_expiring` is not called before the service
        # is started.
        self.assertThat(mark_nodes_failed_after_expiring, MockNotCalled())
        # `mark_nodes_failed_after_expiring` is called the moment the service
        # is started.
        service.startService()
        self.assertThat(mark_nodes_failed_after_expiring, MockCalledOnceWith())
        # Advancing the clock by `interval - 1` means that
        # `mark_nodes_failed_after_expiring` has still only been called once.
        service.clock.advance(interval - 1)
        self.assertThat(mark_nodes_failed_after_expiring, MockCalledOnceWith())
        # Advancing the clock one more second causes another call to
        # `mark_nodes_failed_after_expiring`.
        service.clock.advance(1)
        self.assertThat(
            mark_nodes_failed_after_expiring, MockCallsMatch(call(), call()))

    def test_interval_can_be_set(self):
        interval = self.getUniqueInteger()
        service = StatusMonitorService(interval)
        self.assertEqual(interval, service.step)
