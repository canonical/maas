# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for
:py:module:`~provisioningserver.rackdservices.node_power_monitor_service`."""

from unittest.mock import ANY, Mock, sentinel

from fixtures import FakeLogger
from twisted.internet.defer import fail, succeed
from twisted.internet.error import ConnectionDone
from twisted.internet.task import Clock

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import extract_result, TwistedLoggerFixture
from provisioningserver.rackdservices import node_power_monitor_service as npms
from provisioningserver.rpc import (
    clusterservice,
    exceptions,
    getRegionClient,
    region,
)
from provisioningserver.rpc.testing import MockClusterToRegionRPCFixture


class TestNodePowerMonitorService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def test_init_sets_up_timer_correctly(self):
        service = npms.NodePowerMonitorService()
        self.assertEqual(service.call, (service.try_query_nodes, tuple(), {}))
        self.assertEqual(service.step, 15)
        self.assertIsNone(service.clock)

    def make_monitor_service(self):
        service = npms.NodePowerMonitorService(Clock())
        return service

    def test_query_nodes_calls_the_region(self):
        service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        proto_region, io = rpc_fixture.makeEventLoop(
            region.ListNodePowerParameters
        )
        proto_region.ListNodePowerParameters.return_value = succeed(
            {"nodes": []}
        )

        client = getRegionClient()
        d = service.query_nodes(client)
        io.flush()

        self.assertIsNone(extract_result(d))
        proto_region.ListNodePowerParameters.assert_called_once_with(
            ANY, uuid=client.localIdent
        )

    def test_query_nodes_calls_query_all_nodes(self):
        service = self.make_monitor_service()
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
            region.ListNodePowerParameters
        )
        proto_region.ListNodePowerParameters.side_effect = [
            succeed({"nodes": [example_power_parameters]}),
            succeed({"nodes": []}),
        ]

        query_all_nodes = self.patch(npms, "query_all_nodes")

        d = service.query_nodes(getRegionClient())
        io.flush()

        self.assertIsNone(extract_result(d))
        query_all_nodes.assert_called_once_with(
            [example_power_parameters],
            max_concurrency=sentinel.max_nodes_at_once,
            clock=service.clock,
        )

    def test_query_nodes_copes_with_NoSuchCluster(self):
        service = self.make_monitor_service()

        rpc_fixture = self.useFixture(MockClusterToRegionRPCFixture())
        proto_region, io = rpc_fixture.makeEventLoop(
            region.ListNodePowerParameters
        )
        client = getRegionClient()
        proto_region.ListNodePowerParameters.return_value = fail(
            exceptions.NoSuchCluster.from_uuid(client.localIdent)
        )

        d = service.query_nodes(client)
        d.addErrback(service.query_nodes_failed, client.localIdent)
        with FakeLogger("maas") as maaslog:
            io.flush()

        self.assertIsNone(extract_result(d))
        self.assertIn("Rack controller '' is not recognised.", maaslog.output)

    def test_query_nodes_copes_with_losing_connection_to_region(self):
        service = self.make_monitor_service()

        client = Mock(
            return_value=fail(ConnectionDone("Connection was closed cleanly."))
        )

        with FakeLogger("maas") as maaslog:
            d = service.query_nodes(client)
            d.addErrback(service.query_nodes_failed, sentinel.ident)

        self.assertIsNone(extract_result(d))
        self.assertIn("Lost connection to region controller.", maaslog.output)

    def test_try_query_nodes_logs_other_errors(self):
        service = self.make_monitor_service()
        self.patch(npms, "getRegionClient").return_value = sentinel.client
        sentinel.client.localIdent = factory.make_UUID()

        query_nodes = self.patch(service, "query_nodes")
        query_nodes.return_value = fail(
            ZeroDivisionError("Such a shame I can't divide by zero")
        )

        with FakeLogger("maas") as maaslog, TwistedLoggerFixture():
            d = service.try_query_nodes()

        self.assertIsNone(extract_result(d))
        self.assertIn(
            "Failed to query nodes' power status: Such a shame I can't divide by zero",
            maaslog.output,
        )
