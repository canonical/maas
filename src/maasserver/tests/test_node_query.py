# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node power status query when state changes."""

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
    NODE_STATUS,
    )
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.testing import always_succeed_with
from twisted.internet.task import Clock


class TestStatusQueryEvent(MAASServerTestCase):

    def setUp(self):
        super(TestStatusQueryEvent, self).setUp()
        # Circular imports.
        from maasserver import node_query
        self.node_query = node_query

    def test_changing_status_of_node_emits_event(self):
        mock_update = self.patch(
            self.node_query, 'wait_to_update_power_state_of_node')
        old_status = NODE_STATUS.COMMISSIONING
        node = factory.make_Node(status=old_status, power_type='virsh')
        node.status = get_failed_status(old_status)
        node.save()
        self.assertThat(
            mock_update,
            MockCalledOnceWith(node.system_id))

    def test_changing_not_tracked_status_of_node_doesnt_emit_event(self):
        mock_update = self.patch(
            self.node_query, "wait_to_update_power_state_of_node")
        old_status = NODE_STATUS.ALLOCATED
        node = factory.make_Node(status=old_status, power_type="virsh")
        node.status = NODE_STATUS.DEPLOYING
        node.save()
        self.assertThat(
            mock_update,
            MockNotCalled())


class TestWaitToUpdatePowerStateOfNode(MAASServerTestCase):

    def setUp(self):
        super(TestWaitToUpdatePowerStateOfNode, self).setUp()
        # Circular imports.
        from maasserver import node_query
        self.node_query = node_query

    def test__calls_update_power_state_of_node_after_wait_time(self):
        mock_defer_to_thread = self.patch(self.node_query, 'deferToThread')
        node = factory.make_Node(power_type="virsh")
        clock = Clock()
        self.node_query.wait_to_update_power_state_of_node(
            node.system_id, clock=clock)

        self.expectThat(mock_defer_to_thread, MockNotCalled())
        clock.advance(self.node_query.WAIT_TO_QUERY.total_seconds())
        self.expectThat(
            mock_defer_to_thread,
            MockCalledOnceWith(
                self.node_query.update_power_state_of_node, node.system_id))


class TestUpdatePowerStateOfNode(MAASServerTestCase):

    def setUp(self):
        super(TestUpdatePowerStateOfNode, self).setUp()
        # Circular imports.
        from maasserver import node_query
        self.node_query = node_query

    def prepare_rpc(self, nodegroup, side_effect):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        protocol = self.rpc_fixture.makeCluster(
            nodegroup, cluster_module.PowerQuery)
        protocol.PowerQuery.side_effect = side_effect

    def test__updates_node_power_state(self):
        node = factory.make_Node(power_type="virsh")
        random_state = random.choice(["on", "off"])
        self.prepare_rpc(
            node.nodegroup,
            side_effect=always_succeed_with({"state": random_state}))
        self.node_query.update_power_state_of_node(node.system_id)
        self.assertEqual(random_state, reload_object(node).power_state)

    def test__handles_deleted_node(self):
        node = factory.make_Node(power_type="virsh")
        node.delete()
        self.node_query.update_power_state_of_node(node.system_id)
        #: Test is that no error is raised

    def test__updates_node_power_state_to_error_if_failure(self):
        node = factory.make_Node(power_type="virsh")
        self.prepare_rpc(
            node.nodegroup,
            side_effect=PowerActionFail())
        self.node_query.update_power_state_of_node(node.system_id)
        self.assertEqual("error", reload_object(node).power_state)
