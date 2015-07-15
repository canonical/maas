# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from maastesting.twisted import TwistedLoggerFixture
from mock import (
    ANY,
    sentinel,
)
from provisioningserver.pserv_services import (
    node_power_monitor_service as npms,
)
from provisioningserver.rpc import (
    exceptions,
    getRegionClient,
    region,
)
from provisioningserver.rpc.testing import MockClusterToRegionRPCFixture
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
            step=15, clock=None))

    def make_monitor_service(self):
        cluster_uuid = factory.make_UUID()
        service = npms.NodePowerMonitorService(cluster_uuid, Clock())
        return cluster_uuid, service

    def test_query_nodes_calls_the_region(self):
        cluster_uuid, service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        proto_region, io = rpc_fixture.makeEventLoop(
            region.ListNodePowerParameters)
        proto_region.ListNodePowerParameters.return_value = succeed(
            {"nodes": []})

        d = service.query_nodes(getRegionClient(), cluster_uuid)
        io.flush()

        self.assertEqual(None, extract_result(d))
        self.assertThat(
            proto_region.ListNodePowerParameters,
            MockCalledOnceWith(ANY, uuid=cluster_uuid))

    def test_query_nodes_calls_query_all_nodes(self):
        cluster_uuid, service = self.make_monitor_service()
        service.max_nodes_at_once = sentinel.max_nodes_at_once

        example_power_parameters = {
            "system_id": factory.make_UUID(),
            "hostname": factory.make_hostname(),
            "power_state": factory.make_name("power_state"),
            "power_type": factory.make_name("power_type"),
            "context": {},
        }

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        proto_region, io = rpc_fixture.makeEventLoop(
            region.ListNodePowerParameters)
        proto_region.ListNodePowerParameters.side_effect = [
            succeed({"nodes": [example_power_parameters]}),
            succeed({"nodes": []}),
        ]

        query_all_nodes = self.patch(npms, "query_all_nodes")

        d = service.query_nodes(getRegionClient(), cluster_uuid)
        io.flush()

        self.assertEqual(None, extract_result(d))
        self.assertThat(
            query_all_nodes,
            MockCalledOnceWith(
                [example_power_parameters],
                max_concurrency=sentinel.max_nodes_at_once,
                clock=service.clock))

    def test_query_nodes_copes_with_NoSuchCluster(self):
        cluster_uuid, service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        proto_region, io = rpc_fixture.makeEventLoop(
            region.ListNodePowerParameters)
        proto_region.ListNodePowerParameters.return_value = fail(
            exceptions.NoSuchCluster.from_uuid(cluster_uuid))

        d = service.query_nodes(getRegionClient(), cluster_uuid)
        d.addErrback(service.query_nodes_failed, cluster_uuid)
        with FakeLogger("maas") as maaslog:
            io.flush()

        self.assertEqual(None, extract_result(d))
        self.assertDocTestMatches(
            "Cluster ... is not recognised.", maaslog.output)

    def test_try_query_nodes_logs_other_errors(self):
        cluster_uuid, service = self.make_monitor_service()
        self.patch(npms, "getRegionClient").return_value = sentinel.client

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
