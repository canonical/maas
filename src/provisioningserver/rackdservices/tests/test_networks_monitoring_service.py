# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks monitor."""

__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver import services
from provisioningserver.rackdservices.networks_monitoring_service import (
    RackNetworksMonitoringService,
)
from provisioningserver.rpc import region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from twisted.internet.defer import (
    inlineCallbacks,
    maybeDeferred,
    succeed,
)
from twisted.internet.task import Clock


class TestRackNetworksMonitoringService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(debug=False, timeout=5)

    @inlineCallbacks
    def test_runs_refresh_first_time(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.RequestRackRefresh)
        self.addCleanup((yield connecting))

        rpc_service = services.getServiceNamed('rpc')
        service = RackNetworksMonitoringService(
            rpc_service, Clock(), enable_monitoring=False)

        yield service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.RequestRackRefresh, MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent))

    @inlineCallbacks
    def test_reports_interfaces_to_region(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.UpdateInterfaces)
        self.addCleanup((yield connecting))

        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }

        rpc_service = services.getServiceNamed('rpc')
        service = RackNetworksMonitoringService(
            rpc_service, Clock(), enable_monitoring=False)
        service.getInterfaces = lambda: succeed(interfaces)
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._recorded = {}

        service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.UpdateInterfaces, MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent,
                interfaces=interfaces))

    @inlineCallbacks
    def test_reports_neighbours_to_region(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateInterfaces, region.ReportNeighbours)
        self.addCleanup((yield connecting))
        rpc_service = services.getServiceNamed('rpc')
        service = RackNetworksMonitoringService(
            rpc_service, Clock(), enable_monitoring=False)
        neighbours = [{"ip": factory.make_ip_address()}]
        yield service.reportNeighbours(neighbours)
        self.assertThat(
            protocol.ReportNeighbours, MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent,
                neighbours=neighbours))

    @inlineCallbacks
    def test_asks_region_for_monitoring_state(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateInterfaces, region.GetDiscoveryState)
        self.addCleanup((yield connecting))
        rpc_service = services.getServiceNamed('rpc')
        reactor = Clock()
        service = RackNetworksMonitoringService(
            rpc_service, reactor, enable_monitoring=False)
        protocol.GetDiscoveryState.return_value = {'interfaces': {}}
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._recorded = {}
        yield service.startService()
        yield maybeDeferred(service.getDiscoveryState)
        yield service.stopService()
        self.assertThat(
            protocol.GetDiscoveryState, MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent))
