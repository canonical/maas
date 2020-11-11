# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convenient test mix-in classes."""


from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from provisioningserver.rpc.cluster import GetPreseedData


class PreseedRPCMixin:
    """Set-up a live RPC environment for testing.

    It creates a cluster connected by RPC that responds to the
    `GetPreseedData` call with a simple `NotImplementedError`.

    Tests that mix this in can use their ``rpc_cluster`` attribute (an
    instance of :py:class:`MockLiveRegionToClusterRPCFixture`) to control the
    RPC environment, and their ``nodegroup`` attribute (a ``NodeGroup`` model
    instance) when creating nodes and suchlike to ensure that calls are routed
    towards the testing RPC "cluster".
    """

    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = MockLiveRegionToClusterRPCFixture()
        self.useFixture(self.rpc_fixture)
        # Create a cluster that's connected by RPC that responds to the
        # GetPreseedData call with a simple NotImplementedError.
        self.rpc_rack_controller = factory.make_RackController()
        self.rpc_cluster = self.rpc_fixture.makeCluster(
            self.rpc_rack_controller, GetPreseedData
        )
        self.rpc_cluster.GetPreseedData.side_effect = NotImplementedError()
