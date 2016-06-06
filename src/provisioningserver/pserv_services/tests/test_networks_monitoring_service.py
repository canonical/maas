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
from provisioningserver.pserv_services.networks_monitoring_service import (
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

        yield service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.UpdateInterfaces, MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent,
                interfaces=interfaces))
