# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
    )
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
    )
from provisioningserver.rpc.testing import always_succeed_with
from testtools.matchers import (
    Equals,
    Is,
    )
from twisted.internet.task import Clock
from twisted.internet.threads import deferToThread
from twisted.python.reflect import namedModule

# This import must go last or it won't import; there's some spaghetti imports
# deep in there that unravel if you do this one weird thing.
node_query = namedModule("maasserver.node_query")


class TestStatusQueryEvent(MAASServerTestCase):

    def test_changing_status_of_node_emits_event(self):
        self.patch_autospec(node_query, 'update_power_state_of_node_soon')
        old_status = NODE_STATUS.COMMISSIONING
        node = factory.make_Node(status=old_status, power_type='virsh')
        node.status = get_failed_status(old_status)
        node.save()
        self.assertThat(
            node_query.update_power_state_of_node_soon,
            MockCalledOnceWith(node.system_id))

    def test_changing_not_tracked_status_of_node_doesnt_emit_event(self):
        self.patch_autospec(node_query, "update_power_state_of_node_soon")
        old_status = NODE_STATUS.ALLOCATED
        node = factory.make_Node(status=old_status, power_type="virsh")
        node.status = NODE_STATUS.DEPLOYING
        node.save()
        self.assertThat(
            node_query.update_power_state_of_node_soon,
            MockNotCalled())


class TestUpdatePowerStateOfNodeSoon(MAASServerTestCase):

    def test__calls_update_power_state_of_node_after_wait_time(self):
        self.patch_autospec(node_query, "update_power_state_of_node")
        node = factory.make_Node(power_type="virsh")
        clock = Clock()
        node_query.update_power_state_of_node_soon(node.system_id, clock=clock)
        self.assertThat(
            node_query.update_power_state_of_node,
            MockNotCalled())
        clock.advance(node_query.WAIT_TO_QUERY.total_seconds())
        self.assertThat(
            node_query.update_power_state_of_node,
            MockCalledOnceWith(node.system_id))


class TestUpdatePowerStateOfNode(MAASTransactionServerTestCase):

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
        self.assertThat(
            node_query.update_power_state_of_node(node.system_id),
            Equals(random_state))
        self.assertThat(
            reload_object(node).power_state,
            Equals(random_state))

    def test__handles_already_deleted_node(self):
        node = factory.make_Node(power_type="virsh")
        node.delete()
        self.assertThat(
            node_query.update_power_state_of_node(node.system_id),
            Is(None))  # Denotes that nothing happened.

    def test__handles_node_being_deleted_in_the_middle(self):
        node = factory.make_Node(power_type="virsh", power_state="off")
        self.prepare_rpc(
            node.nodegroup,
            side_effect=always_succeed_with({"state": "on"}))

        def delete_node_then_get_client(uuid):
            from maasserver.rpc import getClientFor
            d = deferToThread(node.delete)  # Auto-commit outside txn.
            d.addCallback(lambda _: getClientFor(uuid))
            return d

        getClientFor = self.patch_autospec(node_query, "getClientFor")
        getClientFor.side_effect = delete_node_then_get_client

        self.assertThat(
            node_query.update_power_state_of_node(node.system_id),
            Is(None))  # Denotes that nothing happened.

    def test__updates_power_state_to_unknown_on_UnknownPowerType(self):
        node = factory.make_Node(power_type="virsh")
        self.prepare_rpc(node.nodegroup, side_effect=UnknownPowerType())
        self.expectThat(
            node_query.update_power_state_of_node(node.system_id),
            Equals("unknown"))
        self.expectThat(
            reload_object(node).power_state,
            Equals("unknown"))

    def test__updates_power_state_to_unknown_on_NotImplementedError(self):
        node = factory.make_Node(power_type="virsh")
        self.prepare_rpc(node.nodegroup, side_effect=NotImplementedError())
        self.expectThat(
            node_query.update_power_state_of_node(node.system_id),
            Equals("unknown"))
        self.expectThat(
            reload_object(node).power_state,
            Equals("unknown"))

    def test__does_nothing_on_PowerActionAlreadyInProgress(self):
        node = factory.make_Node(power_type="virsh", power_state="off")
        self.prepare_rpc(
            node.nodegroup, side_effect=PowerActionAlreadyInProgress())
        self.expectThat(
            node_query.update_power_state_of_node(node.system_id),
            Is(None))  # Denotes that nothing happened.
        self.expectThat(
            reload_object(node).power_state,
            Equals("off"))

    def test__does_nothing_on_NoConnectionsAvailable(self):
        node = factory.make_Node(power_type="virsh", power_state="off")
        self.prepare_rpc(node.nodegroup, side_effect=None)
        getClientFor = self.patch_autospec(node_query, "getClientFor")
        getClientFor.side_effect = NoConnectionsAvailable()
        self.expectThat(
            node_query.update_power_state_of_node(node.system_id),
            Is(None))  # Denotes that nothing happened.
        self.expectThat(
            reload_object(node).power_state,
            Equals("off"))

    def test__updates_power_state_to_error_on_PowerActionFail(self):
        node = factory.make_Node(power_type="virsh")
        self.prepare_rpc(node.nodegroup, side_effect=PowerActionFail())
        self.expectThat(
            node_query.update_power_state_of_node(node.system_id),
            Equals("error"))
        self.expectThat(
            reload_object(node).power_state,
            Equals("error"))

    def test__updates_power_state_to_error_on_other_error(self):
        node = factory.make_Node(power_type="virsh")
        self.prepare_rpc(node.nodegroup, side_effect=factory.make_exception())
        self.assertThat(
            node_query.update_power_state_of_node(node.system_id),
            Equals("error"))
        self.expectThat(
            reload_object(node).power_state,
            Equals("error"))
