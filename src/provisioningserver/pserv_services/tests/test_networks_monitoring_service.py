# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks monitor."""

__all__ = []


from maastesting.factory import factory
from maastesting.matchers import (
    get_mock_calls,
    HasLength,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTwistedRunTest
from mock import (
    Mock,
    sentinel,
)
from provisioningserver.pserv_services import networks_monitoring_service
from provisioningserver.pserv_services.networks_monitoring_service import (
    NetworksMonitoringService,
)
from provisioningserver.rpc import (
    getRegionClient,
    region,
)
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.testing.testcase import PservTestCase
from twisted.internet import defer
from twisted.internet.task import Clock


class TestNetworksMonitorService(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(region.UpdateInterfaces)
        return protocol, connecting

    def test_is_called_every_interval(self):
        clock = Clock()
        service = NetworksMonitoringService(
            sentinel.service, clock)

        # Avoid actually updating.
        updateInterfaces = self.patch(
            service, 'updateInterfaces')

        # Until the service has started, periodic updateInterfaces()
        # won't be called.
        self.assertThat(updateInterfaces, MockNotCalled())

        # The first call is issued at startup.
        service.startService()
        self.assertThat(updateInterfaces, MockCalledOnceWith())

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)

        # No more periodic calls made.
        self.assertEqual(1, len(get_mock_calls(updateInterfaces)))

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertThat(
            get_mock_calls(updateInterfaces), HasLength(2))

    def test_get_interfaces_definition_is_initiated_in_new_thread(self):
        clock = Clock()
        rpc_service = Mock()
        deferToThread = self.patch(
            networks_monitoring_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(({}, False))
        service = NetworksMonitoringService(rpc_service, clock)
        service.startService()
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                networks_monitoring_service.get_interfaces_definition))

    def test_logs_errors(self):
        clock = Clock()
        maaslog = self.patch(networks_monitoring_service, 'maaslog')
        service = NetworksMonitoringService(
            sentinel.service, clock)
        error_message = factory.make_string()
        self.patch(service, 'updateInterfaces').side_effect = Exception(
            error_message)
        service.startService()
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Failed to update region about the interface "
                "configuration: %s",
                error_message))

    @defer.inlineCallbacks
    def test_calls_clear_current_interfaces_when_fails_to_send_to_region(self):
        clock = Clock()
        clear_current_interfaces_definition = self.patch(
            networks_monitoring_service, 'clear_current_interfaces_definition')
        get_interfaces_definition = self.patch(
            networks_monitoring_service, 'get_interfaces_definition')
        get_interfaces_definition.return_value = ({}, True)

        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        del protocol._commandDispatch[
            region.UpdateInterfaces.commandName]
        rpc_service = Mock()
        rpc_service.getClient.return_value = getRegionClient()
        service = NetworksMonitoringService(rpc_service, clock)
        yield service.startService()
        yield service.stopService()
        self.assertThat(
            clear_current_interfaces_definition, MockCalledOnceWith())

    @defer.inlineCallbacks
    def test_reports_interfaces_to_region(self):
        clock = Clock()
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        deferToThread = self.patch(
            networks_monitoring_service, 'deferToThread')
        interfaces = {
            "eth0": {
                "type": "physical",
                "mac_address": factory.make_mac_address(),
                "parents": [],
                "links": [],
                "enabled": True,
            }
        }
        deferToThread.return_value = defer.succeed((interfaces, True))

        client = getRegionClient()
        rpc_service = Mock()
        rpc_service.getClient.return_value = client

        service = NetworksMonitoringService(
            rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.UpdateInterfaces,
            MockCalledOnceWith(
                protocol,
                system_id=client.localIdent,
                interfaces=interfaces))
