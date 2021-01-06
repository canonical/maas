# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks monitor."""


from unittest.mock import call, Mock

from twisted.internet.defer import inlineCallbacks, maybeDeferred, succeed
from twisted.internet.task import Clock

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import services
from provisioningserver.rackdservices.networks_monitoring_service import (
    RackNetworksMonitoringService,
)
from provisioningserver.rpc import clusterservice, region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils import services as services_module


class TestRackNetworksMonitoringService(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(debug=True, timeout=5)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    @inlineCallbacks
    def test_runs_refresh_first_time(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.RequestRackRefresh)
        self.addCleanup((yield connecting))

        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=False,
        )
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        service.getInterfaces = lambda: succeed(interfaces)
        yield maybeDeferred(service.startService)
        # By stopping the interface_monitor first, we assure that the loop
        # happens at least once before the service stops completely.
        yield maybeDeferred(service.interface_monitor.stopService)
        yield maybeDeferred(service.stopService)

        self.assertThat(
            protocol.RequestRackRefresh,
            MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent
            ),
        )

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

        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=False,
        )
        service.getInterfaces = lambda: succeed(interfaces)
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._recorded = {}

        service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.UpdateInterfaces,
            MockCalledOnceWith(
                protocol,
                system_id=rpc_service.getClient().localIdent,
                interfaces=interfaces,
                topology_hints=None,
            ),
        )

    @inlineCallbacks
    def test_reports_interfaces_with_hints_if_beaconing_enabled(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.UpdateInterfaces)
        # Don't actually wait for beaconing to complete.
        pause_mock = self.patch(services_module, "pause")
        queue_mcast_mock = self.patch(
            services_module.BeaconingSocketProtocol, "queueMulticastBeaconing"
        )
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

        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=True,
        )
        service.getInterfaces = lambda: succeed(interfaces)
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._recorded = {}

        service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.UpdateInterfaces,
            MockCalledOnceWith(
                protocol,
                system_id=rpc_service.getClient().localIdent,
                interfaces=interfaces,
                topology_hints=[],
            ),
        )
        # The service should have sent out beacons, waited three seconds,
        # solicited for more beacons, then waited another three seconds before
        # deciding that beaconing is complete.
        self.assertThat(pause_mock, MockCallsMatch(call(3.0), call(3.0)))
        self.assertThat(
            queue_mcast_mock,
            MockCallsMatch(
                # Called when the service starts.
                call(solicitation=True),
                # Called three seconds later.
                call(solicitation=True),
                # Not called again when the service shuts down.
            ),
        )

    @inlineCallbacks
    def test_reports_neighbours_to_region(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateInterfaces, region.ReportNeighbours
        )
        self.addCleanup((yield connecting))
        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=False,
        )
        neighbours = [{"ip": factory.make_ip_address()}]
        yield service.reportNeighbours(neighbours)
        self.assertThat(
            protocol.ReportNeighbours,
            MockCalledOnceWith(
                protocol,
                system_id=rpc_service.getClient().localIdent,
                neighbours=neighbours,
            ),
        )

    @inlineCallbacks
    def test_reports_mdns_to_region(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateInterfaces, region.ReportMDNSEntries
        )
        self.addCleanup((yield connecting))
        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=False,
        )
        mdns = [
            {
                "interface": "eth0",
                "hostname": "boggle.example.com",
                "address": factory.make_ip_address(),
            }
        ]
        yield service.reportMDNSEntries(mdns)
        self.assertThat(
            protocol.ReportMDNSEntries,
            MockCalledOnceWith(
                protocol,
                system_id=rpc_service.getClient().localIdent,
                mdns=mdns,
            ),
        )

    @inlineCallbacks
    def test_asks_region_for_monitoring_state(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateInterfaces, region.GetDiscoveryState
        )
        self.addCleanup((yield connecting))
        rpc_service = services.getServiceNamed("rpc")
        reactor = Clock()
        service = RackNetworksMonitoringService(
            rpc_service,
            reactor,
            enable_monitoring=False,
            enable_beaconing=False,
        )
        protocol.GetDiscoveryState.return_value = {"interfaces": {}}
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._recorded = {}
        yield service.startService()
        yield maybeDeferred(service.getDiscoveryState)
        yield service.stopService()
        self.assertThat(
            protocol.GetDiscoveryState,
            MockCalledOnceWith(
                protocol, system_id=rpc_service.getClient().localIdent
            ),
        )

    @inlineCallbacks
    def test_requests_beaconing_when_timer_fires(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateInterfaces, region.GetDiscoveryState
        )
        self.addCleanup((yield connecting))
        rpc_service = services.getServiceNamed("rpc")
        reactor = Clock()
        service = RackNetworksMonitoringService(
            rpc_service,
            reactor,
            enable_monitoring=False,
            enable_beaconing=True,
        )
        service.beaconing_protocol = Mock()
        service.beaconing_protocol.queueMulticastBeaconing = Mock()
        service.getInterfaces = lambda: succeed({})
        service._recorded = {}
        service.startService()
        yield service.stopService()
        self.assertThat(
            service.beaconing_protocol.queueMulticastBeaconing,
            MockCallsMatch(call(solicitation=True)),
        )
