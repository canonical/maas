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
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.rpc.timers import handle_timer_expired
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maastesting.testcase import MAASTestCase
from provisioningserver.enum import TIMER_TYPE
from provisioningserver.rpc.cluster import CancelTimer


class TestHandleTimerExpired(MAASTestCase):

    def prepare_cluster_rpc(self, cluster):
        self.useFixture(RegionEventLoopFixture('rpc'))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = fixture.makeCluster(cluster, CancelTimer)
        return protocol

    def test_handle_timer_expired(self):
        status = random.choice(NODE_FAILURE_STATUS_TRANSITIONS.keys())
        node = factory.make_Node(status=status)
        monitor_timeout = random.randint(1, 100)
        context = {
            'timeout': monitor_timeout,
            'node_status': node.status,
            'type': TIMER_TYPE.NODE_STATE_CHANGE,
        }
        self.prepare_cluster_rpc(node.nodegroup)

        handle_timer_expired(node.system_id, context)

        self.assertEqual(
            get_failed_status(status),
            reload_object(node).status)
