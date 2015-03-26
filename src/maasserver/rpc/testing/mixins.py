# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convenient test mix-in classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "PreseedRPCMixin",
]

from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from provisioningserver.rpc.cluster import (
    ComposeCurtinNetworkPreseed,
    GetPreseedData,
)
from provisioningserver.rpc.testing import always_succeed_with


class PreseedRPCMixin:
    """Set-up a live RPC environment for testing.

    It creates a cluster connected by RPC that responds to the
    `GetPreseedData` call with a simple `NotImplementedError`.  The
    `ComposeCurtinNetworkPreseed` call returns an empty list.

    Tests that mix this in can use their ``rpc_cluster`` attribute (an
    instance of :py:class:`MockLiveRegionToClusterRPCFixture`) to control the
    RPC environment, and their ``nodegroup`` attribute (a ``NodeGroup`` model
    instance) when creating nodes and suchlike to ensure that calls are routed
    towards the testing RPC "cluster".
    """

    def setUp(self):
        super(PreseedRPCMixin, self).setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = MockLiveRegionToClusterRPCFixture()
        self.useFixture(self.rpc_fixture)
        # Create a cluster that's connected by RPC that responds to the
        # GetPreseedData call with a simple NotImplementedError.
        self.rpc_nodegroup = factory.make_NodeGroup()
        self.rpc_cluster = self.rpc_fixture.makeCluster(
            self.rpc_nodegroup, GetPreseedData, ComposeCurtinNetworkPreseed)
        self.rpc_cluster.GetPreseedData.side_effect = (
            NotImplementedError())
        self.rpc_cluster.ComposeCurtinNetworkPreseed.side_effect = (
            always_succeed_with({'data': []}))
