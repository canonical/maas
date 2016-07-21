# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for periodic DHCP prober."""

__all__ = []


from unittest.mock import (
    call,
    Mock,
    sentinel,
)

from maastesting.factory import factory
from maastesting.matchers import (
    get_mock_calls,
    HasLength,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTwistedRunTest
from provisioningserver.rackdservices import dhcp_probe_service
from provisioningserver.rackdservices.dhcp_probe_service import (
    DHCPProbeService,
)
from provisioningserver.rpc import (
    getRegionClient,
    region,
)
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.testing.testcase import PservTestCase
from twisted.internet import defer
from twisted.internet.task import Clock


class TestDHCPProbeService(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.ReportForeignDHCPServer)
        return protocol, connecting

    def test_is_called_every_interval(self):
        clock = Clock()
        service = DHCPProbeService(
            sentinel.service, clock)

        # Avoid actually probing
        probe_dhcp = self.patch(service, 'probe_dhcp')

        # Until the service has started, periodicprobe_dhcp() won't
        # be called.
        self.assertThat(probe_dhcp, MockNotCalled())

        # The first call is issued at startup.
        service.startService()
        self.assertThat(probe_dhcp, MockCalledOnceWith())

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)

        # No more periodic calls made.
        self.assertEqual(1, len(get_mock_calls(probe_dhcp)))

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertThat(get_mock_calls(probe_dhcp), HasLength(2))

    def test_probe_is_initiated_in_new_thread(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
            }
        }

        deferToThread = self.patch(dhcp_probe_service, 'deferToThread')
        deferToThread.side_effect = [
            defer.succeed(interfaces),
            defer.succeed(None),
        ]
        service = DHCPProbeService(Mock(), clock)
        service.startService()
        self.assertThat(
            deferToThread, MockCallsMatch(
                call(dhcp_probe_service.get_all_interfaces_definition),
                call(dhcp_probe_service.probe_interface, interface_name)))

    @defer.inlineCallbacks
    def test_exits_gracefully_if_cant_report_foreign_dhcp_server(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
            }
        }

        maaslog = self.patch(dhcp_probe_service, 'maaslog')
        deferToThread = self.patch(
            dhcp_probe_service, 'deferToThread')
        deferToThread.side_effect = [
            defer.succeed(interfaces),
            defer.succeed(['192.168.0.100']),
        ]
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        del protocol._commandDispatch[
            region.ReportForeignDHCPServer.commandName]

        rpc_service = Mock()
        rpc_service.getClient.return_value = getRegionClient()
        service = DHCPProbeService(
            rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to inform region of DHCP server: the region "
                "does not yet support the ReportForeignDHCPServer RPC "
                "method."))

    def test_logs_errors(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
            }
        }

        maaslog = self.patch(dhcp_probe_service, 'maaslog')
        mock_interfaces = self.patch(
            dhcp_probe_service, 'get_all_interfaces_definition')
        mock_interfaces.return_value = interfaces
        service = DHCPProbeService(
            sentinel.service, clock)
        error_message = factory.make_string()
        self.patch(service, 'probe_dhcp').side_effect = Exception(
            error_message)
        service.startService()
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to probe for DHCP servers: %s",
                error_message))

    @defer.inlineCallbacks
    def test_reports_foreign_dhcp_servers_to_region(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
            }
        }

        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        deferToThread = self.patch(
            dhcp_probe_service, 'deferToThread')
        foreign_dhcp_ip = factory.make_ipv4_address()
        deferToThread.side_effect = [
            defer.succeed(interfaces),
            defer.succeed([foreign_dhcp_ip]),
        ]

        client = getRegionClient()
        rpc_service = Mock()
        rpc_service.getClient.return_value = client

        service = DHCPProbeService(
            rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.ReportForeignDHCPServer,
            MockCalledOnceWith(
                protocol,
                system_id=client.localIdent,
                interface_name=interface_name,
                dhcp_ip=foreign_dhcp_ip))

    @defer.inlineCallbacks
    def test_reports_lack_of_foreign_dhcp_servers_to_region(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
            }
        }

        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        deferToThread = self.patch(
            dhcp_probe_service, 'deferToThread')
        deferToThread.side_effect = [
            defer.succeed(interfaces),
            defer.succeed([]),
        ]

        client = getRegionClient()
        rpc_service = Mock()
        rpc_service.getClient.return_value = client
        service = DHCPProbeService(
            rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        self.assertThat(
            protocol.ReportForeignDHCPServer,
            MockCalledOnceWith(
                protocol,
                system_id=client.localIdent,
                interface_name=interface_name,
                dhcp_ip=None))
