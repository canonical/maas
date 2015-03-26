# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for
:py:module:`~provisioningserver.pserv_services.node_power_monitor_service`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import (
    ANY,
    call,
)
from provisioningserver.pserv_services import (
    node_power_monitor_service as npms,
)
from provisioningserver.rpc import (
    exceptions,
    region,
)
from provisioningserver.rpc.testing import (
    MockClusterToRegionRPCFixture,
    TwistedLoggerFixture,
)
from testtools.deferredruntest import extract_result
from testtools.matchers import MatchesStructure
from twisted.internet.defer import (
    fail,
    succeed,
)
from twisted.internet.task import Clock


class TestNodePowerMonitorService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_init_sets_up_timer_correctly(self):
        cluster_uuid = factory.make_UUID()
        service = npms.NodePowerMonitorService(cluster_uuid)
        self.assertThat(service, MatchesStructure.byEquality(
            call=(service.try_query_nodes, (cluster_uuid,), {}),
            step=(5 * 60), clock=None))

    def make_monitor_service(self):
        cluster_uuid = factory.make_UUID()
        service = npms.NodePowerMonitorService(cluster_uuid, Clock())
        return cluster_uuid, service

    def test_query_nodes_retries_getting_client(self):
        cluster_uuid, service = self.make_monitor_service()

        getRegionClient = self.patch(npms, "getRegionClient")
        getRegionClient.side_effect = exceptions.NoConnectionsAvailable

        def has_been_called_n_times(n):
            calls = [call()] * n
            return MockCallsMatch(*calls)

        maaslog = self.useFixture(FakeLogger("maas"))

        d = service.query_nodes(cluster_uuid)
        # Immediately the first attempt to get a client happens.
        self.assertThat(getRegionClient, has_been_called_n_times(1))
        self.assertFalse(d.called)
        # Followed by 3 more attempts as time passes.
        service.clock.pump((5, 5, 5))
        self.assertThat(getRegionClient, has_been_called_n_times(4))
        # query_nodes returns after 15 seconds.
        self.assertTrue(d.called)
        self.assertIsNone(extract_result(d))

        # A simple message is logged, but even this may be too noisy.
        self.assertIn(
            "Cannot monitor nodes' power status; region not available.",
            maaslog.output)

    def test_query_nodes_calls_the_region(self):
        cluster_uuid, service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        client, io = rpc_fixture.makeEventLoop(region.ListNodePowerParameters)
        client.ListNodePowerParameters.return_value = succeed({"nodes": []})

        d = service.query_nodes(cluster_uuid)
        io.flush()

        self.assertEqual(None, extract_result(d))
        self.assertThat(
            client.ListNodePowerParameters,
            MockCalledOnceWith(ANY, uuid=cluster_uuid))

    def test_query_nodes_calls_query_all_nodes(self):
        cluster_uuid, service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        client, io = rpc_fixture.makeEventLoop(region.ListNodePowerParameters)
        client.ListNodePowerParameters.return_value = succeed({"nodes": []})

        query_all_nodes = self.patch(npms, "query_all_nodes")

        d = service.query_nodes(cluster_uuid)
        io.flush()

        self.assertEqual(None, extract_result(d))
        self.assertThat(
            query_all_nodes,
            MockCalledOnceWith(
                [], max_concurrency=service.max_nodes_at_once,
                clock=service.clock))

    def test_query_nodes_copes_with_NoSuchCluster(self):
        cluster_uuid, service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        client, io = rpc_fixture.makeEventLoop(region.ListNodePowerParameters)
        client.ListNodePowerParameters.return_value = fail(
            exceptions.NoSuchCluster.from_uuid(cluster_uuid))

        d = service.query_nodes(cluster_uuid)
        with FakeLogger("maas") as maaslog:
            io.flush()

        self.assertEqual(None, extract_result(d))
        self.assertDocTestMatches(
            "This cluster (...) is not recognised by the region.",
            maaslog.output)

    def test_try_query_nodes_logs_other_errors(self):
        cluster_uuid, service = self.make_monitor_service()

        query_nodes = self.patch(service, "query_nodes")
        query_nodes.return_value = fail(
            ZeroDivisionError("Such a shame I can't divide by zero"))

        with FakeLogger("maas") as maaslog, TwistedLoggerFixture():
            d = service.try_query_nodes(cluster_uuid)

        self.assertEqual(None, extract_result(d))
        self.assertDocTestMatches(
            "Failed to query nodes' power status: "
            "Such a shame I can't divide by zero",
            maaslog.output)
