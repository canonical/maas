# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for :py:mod:`maasserver.clusterrpc.power`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.clusterrpc.power import (
    power_off_node,
    power_on_node,
)
from maasserver.rpc.testing.fixtures import MockRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from mock import ANY
from provisioningserver.rpc.cluster import (
    PowerOff,
    PowerOn,
)
from provisioningserver.utils.twisted import reactor_sync
from testtools.deferredruntest import extract_result


class TestPowerNode(MAASServerTestCase):
    """Tests for `power_on_node` and `power_off_node`."""

    scenarios = (
        ("PowerOn", {"power_func": power_on_node, "command": PowerOn}),
        ("PowerOff", {"power_func": power_off_node, "command": PowerOff}),
    )

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockRegionToClusterRPCFixture())

    def test__powers_single_node(self):
        rpc_fixture = self.prepare_rpc()

        node = factory.make_Node()
        cluster, io = rpc_fixture.makeCluster(node.nodegroup, self.command)

        # We're not doing any IO via the reactor so we sync with it only so
        # that this becomes the IO thread, making @asynchronous transparent.
        with reactor_sync():
            d = self.power_func(
                node.system_id, node.hostname, node.nodegroup.uuid,
                node.get_effective_power_info())

        io.flush()
        self.assertEquals({}, extract_result(d))

        power_info = node.get_effective_power_info()
        self.assertThat(
            getattr(cluster, self.command.commandName),
            MockCalledOnceWith(
                ANY, system_id=node.system_id, hostname=node.hostname,
                power_type=power_info.power_type,
                context=power_info.power_parameters,
            ))
