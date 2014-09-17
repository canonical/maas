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

from maasserver import timer_connect
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
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import ANY
from provisioningserver.rpc.cluster import CancelTimer


class TestCancelTimer(MAASTestCase):

    def setUp(self):
        super(TestCancelTimer, self).setUp()
        self.patch(timer_connect, 'TIMER_CANCEL_CONNECT', True)

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockLiveRegionToClusterRPCFixture())

    def test_changing_status_of_monitored_node_cancels_related_timer(self):
        rpc_fixture = self.prepare_rpc()
        status = random.choice(MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        cluster = rpc_fixture.makeCluster(node.nodegroup, CancelTimer)
        node.status = get_failed_status(status)
        node.save()

        self.assertThat(
            cluster.CancelTimer,
            MockCalledOnceWith(ANY, id=node.system_id))
