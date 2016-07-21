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
    succeed,
)
from twisted.internet.task import Clock


class TestRackNetworksMonitoringService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_runs_refresh_first_time(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.RequestRackRefresh)
        self.addCleanup((yield connecting))

        rpc_service = services.getServiceNamed('rpc')
        service = RackNetworksMonitoringService(rpc_service, Clock())

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
        service = RackNetworksMonitoringService(rpc_service, Clock())
        service.getInterfaces = lambda: succeed(interfaces)
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._interfacesRecorded({})

        yield service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.UpdateInterfaces, MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent,
                interfaces=interfaces))
