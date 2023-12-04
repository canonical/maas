# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from unittest.mock import call, Mock

from twisted.internet.defer import (
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    succeed,
)
from twisted.internet.task import Clock

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import services
from provisioningserver.rackdservices.networks_monitoring_service import (
    RackNetworksMonitoringService,
)
from provisioningserver.rpc import clusterservice, region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.utils import services as services_module


class TestRackNetworksMonitoringService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        debug=True, timeout=get_testing_timeout()
    )

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}
        self.mock_refresh = self.patch(services_module, "refresh")
        self.metadata_creds = {
            "consumer_key": factory.make_string(),
            "token_key": factory.make_string(),
            "token_secret": factory.make_string(),
        }

    @inlineCallbacks
    def create_fake_rpc_service(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.RequestRackRefresh)
        self.addCleanup((yield connecting))
        protocol.RequestRackRefresh.return_value = self.metadata_creds
        returnValue(protocol)

    @inlineCallbacks
    def test_get_refresh_details_not_running(self):
        yield self.create_fake_rpc_service()
        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=False,
        )
        service.running = 0
        details = yield service.getRefreshDetails()
        self.assertEqual((None, None, None), details)

    @inlineCallbacks
    def test_get_refresh_details_running(self):
        yield self.create_fake_rpc_service()
        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=False,
        )
        service.running = 1
        self.metadata_creds.update(
            {
                "consumer_key": "my-key",
                "token_key": "my-token",
                "token_secret": "my-secret",
            }
        )
        details = yield service.getRefreshDetails()
        self.assertEqual(
            ("http://localhost/MAAS", "", self.metadata_creds), details
        )

    @inlineCallbacks
    def test_reports_interfaces_to_region(self):
        def refresh(
            system_id,
            consumer_key,
            token_key,
            token_secret,
            maas_url=None,
            post_process_hook=None,
        ):
            self.assertEqual("", system_id)
            self.assertEqual(self.metadata_creds["consumer_key"], consumer_key)
            self.assertEqual(self.metadata_creds["token_key"], token_key)
            self.assertEqual(self.metadata_creds["token_secret"], token_secret)
            self.assertEqual("http://localhost/MAAS", maas_url)

        yield self.create_fake_rpc_service()
        self.mock_refresh.side_effect = refresh

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
        clock = Clock()
        service = RackNetworksMonitoringService(
            rpc_service,
            clock,
            enable_monitoring=False,
            enable_beaconing=False,
        )
        service.getInterfaces = lambda: succeed(interfaces)
        # Put something in the cache. This tells recordInterfaces that refresh
        # has already run but the interfaces have changed thus they need to be
        # updated.
        service._recorded = {}

        service.startService()
        clock.advance(0)
        yield service.stopService()

        self.assertEqual(1, self.mock_refresh.call_count)

    @inlineCallbacks
    def test_reports_interfaces_with_hints_if_beaconing_enabled(self):
        yield self.create_fake_rpc_service()
        # Don't actually wait for beaconing to complete.
        pause_mock = self.patch(services_module, "pause")
        queue_mcast_mock = self.patch(
            services_module.BeaconingSocketProtocol, "queueMulticastBeaconing"
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

        rpc_service = services.getServiceNamed("rpc")
        service = RackNetworksMonitoringService(
            rpc_service,
            Clock(),
            enable_monitoring=False,
            enable_beaconing=True,
        )
        service.getInterfaces = lambda: succeed(interfaces)

        service.startService()
        # By stopping the TimerService first, we assure that the loop
        # happens at least once before the service stops completely.
        yield maybeDeferred(service._timer_service.stopService)
        yield service.stopService()

        # The service should have sent out beacons, waited three seconds,
        # solicited for more beacons, then waited another three seconds before
        # deciding that beaconing is complete.
        pause_mock.assert_has_calls([call(3.0), call(3.0)])
        queue_mcast_mock.assert_has_calls(
            [
                # Called when the service starts.
                call(solicitation=True),
                # Called three seconds later.
                call(solicitation=True),
                # Not called again when the service shuts down.
            ],
        )

    @inlineCallbacks
    def test_reports_neighbours_to_region(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.ReportNeighbours)
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
        protocol.ReportNeighbours.assert_called_once_with(
            protocol,
            system_id=rpc_service.getClient().localIdent,
            neighbours=neighbours,
        )

    @inlineCallbacks
    def test_reports_mdns_to_region(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.ReportMDNSEntries)
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
        protocol.ReportMDNSEntries.assert_called_once_with(
            protocol,
            system_id=rpc_service.getClient().localIdent,
            mdns=mdns,
        )

    @inlineCallbacks
    def test_asks_region_for_monitoring_state(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.GetDiscoveryState)
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
        protocol.GetDiscoveryState.assert_called_once_with(
            protocol, system_id=rpc_service.getClient().localIdent
        )

    @inlineCallbacks
    def test_requests_beaconing_when_timer_fires(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.GetDiscoveryState)
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
        service.beaconing_protocol.queueMulticastBeaconing.assert_has_calls(
            [call(solicitation=True)]
        )
