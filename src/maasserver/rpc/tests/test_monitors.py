# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

import random

from maasserver.node_status import (
    get_failed_status,
    NODE_FAILURE_STATUS_TRANSITIONS,
    )
from maasserver.rpc.monitors import handle_monitor_expired
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc.cluster import CancelMonitor


class TestHandleMonitorExpired(MAASTestCase):

    def prepare_cluster_rpc(self, cluster):
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(cluster, CancelMonitor)
        return protocol

    def test_handle_monitor_expired(self):
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
