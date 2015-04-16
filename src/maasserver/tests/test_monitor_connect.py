# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for timer-related signals."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import random
import threading

from maasserver.node_status import (
    get_failed_status,
    MONITORED_STATUSES,
)
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from maastesting.matchers import MockCalledOnceWith
from mock import ANY
from provisioningserver.rpc.cluster import CancelMonitor
from twisted.internet import defer


class TestCancelMonitor(MAASServerTestCase):

    def setUp(self):
        super(TestCancelMonitor, self).setUp()
        # Circular imports.
        from maasserver import monitor_connect
        self.patch(monitor_connect, 'MONITOR_CANCEL_CONNECT', True)

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockLiveRegionToClusterRPCFixture())

    def test_changing_status_of_monitored_node_cancels_related_monitor(self):
        from maasserver import node_query  # Circular import.
        self.addCleanup(node_query.enable)
        node_query.disable()

        done = threading.Event()
        rpc_fixture = self.prepare_rpc()
        status = random.choice(MONITORED_STATUSES)
        node = factory.make_Node(status=status)

        def handle(self, id):
            done.set()  # Tell the calling thread.
            return defer.succeed({})

        cluster = rpc_fixture.makeCluster(node.nodegroup, CancelMonitor)
        cluster.CancelMonitor.side_effect = handle

        node.status = get_failed_status(status)
        node.save()
        post_commit_hooks.fire()

        self.assertTrue(done.wait(5))
        self.assertThat(
            cluster.CancelMonitor,
            MockCalledOnceWith(ANY, id=node.system_id))
