# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for RPC utility functions for timers."""

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
import random
from random import randint

import crochet
from maasserver.models.signals import power as node_query
from maasserver.node_status import (
    get_failed_status,
    NODE_FAILURE_STATUS_TRANSITIONS,
)
from maasserver.rpc import monitors
from maasserver.rpc.monitors import (
    handle_monitor_expired,
    TransitionMonitor,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
)
from provisioningserver.rpc.cluster import (
    CancelMonitor,
    StartMonitors,
)
from testtools.matchers import (
    Equals,
    Is,
    MatchesStructure,
    Not,
)
from twisted.internet.defer import succeed
from twisted.protocols import amp

# Ensure that the reactor is running; one or more tests need it.
crochet.setup()


class TestHandleMonitorExpired(MAASServerTestCase):

    def prepare_cluster_rpc(self, cluster):
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(cluster, CancelMonitor)
        return protocol

    def test_handle_monitor_expired(self):
        self.addCleanup(node_query.enable)
        node_query.disable()

        status = random.choice(NODE_FAILURE_STATUS_TRANSITIONS.keys())
        node = factory.make_Node(status=status)
        monitor_timeout = random.randint(1, 100)
        context = {
            'timeout': monitor_timeout,
            'node_status': node.status,
        }
        self.prepare_cluster_rpc(node.nodegroup)

        handle_monitor_expired(node.system_id, context)

        self.assertEqual(
            get_failed_status(status),
            reload_object(node).status)


class TestTransitionMonitor(MAASTestCase):
    """Tests for `TransitionMonitor`."""

    def test_init(self):
        monitor = TransitionMonitor(
            sentinel.nodegroup_uuid, sentinel.system_id)
        self.assertThat(monitor, MatchesStructure.byEquality(
            nodegroup_uuid=sentinel.nodegroup_uuid,
            system_id=sentinel.system_id, status=None, timeout=None))

    def test__within_returns_new_monitor(self):
        timeout = randint(1, 1000)
        monitor = TransitionMonitor(sentinel.ngid, sentinel.sid)
        monitor_within = monitor.within(timeout)
        self.expectThat(monitor_within, Not(Is(monitor)))
        self.expectThat(
            monitor_within.timeout,
            Equals(timedelta(seconds=timeout)))
        self.expectThat(monitor.timeout, Is(None))

    def test__status_should_be_returns_new_monitor(self):
        status = randint(1, 1000)
        monitor = TransitionMonitor(sentinel.ngid, sentinel.sid)
        monitor_within = monitor.status_should_be(status)
        self.expectThat(monitor_within, Not(Is(monitor)))
        self.expectThat(monitor_within.status, Equals(status))
        self.expectThat(monitor.status, Is(None))

    def test__start_calls_StartMonitors(self):
        timeout, status = randint(1, 1000), randint(1, 1000)
        monitor = TransitionMonitor(sentinel.ngid, sentinel.sid)
        monitor = monitor.within(timeout).status_should_be(status)

        client = Mock()
        client.return_value = succeed(sentinel.okay)

        getClientFor = self.patch_autospec(monitors, "getClientFor")
        getClientFor.return_value = succeed(client)

        monitors_datetime = self.patch_autospec(monitors, "datetime")
        monitors_datetime.now.return_value = now = datetime.now(amp.utc)

        self.assertThat(monitor.start(), Is(sentinel.okay))
        self.assertThat(getClientFor, MockCalledOnceWith(sentinel.ngid))
        self.assertThat(client, MockCalledOnceWith(
            StartMonitors, monitors=[{
                "context": {"node_status": status, "timeout": timeout},
                "deadline": now + timedelta(seconds=timeout),
                "id": sentinel.sid,
            }]))

    def test__stop_calls_CancelMonitor(self):
        monitor = TransitionMonitor(sentinel.ngid, sentinel.sid)

        client = Mock()
        client.return_value = succeed(sentinel.okay)

        getClientFor = self.patch_autospec(monitors, "getClientFor")
        getClientFor.return_value = succeed(client)

        self.assertThat(monitor.stop(), Is(sentinel.okay))
        self.assertThat(getClientFor, MockCalledOnceWith(sentinel.ngid))
        self.assertThat(client, MockCalledOnceWith(
            CancelMonitor, id=sentinel.sid))
