# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for periodic DHCP prober."""


from unittest.mock import Mock, sentinel

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.rackdservices import dhcp_probe_service
from provisioningserver.rackdservices.dhcp_probe_service import (
    DHCPProbeService,
)
from provisioningserver.rpc import clusterservice, getRegionClient, region
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture


class TestDHCPProbeService(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.ReportForeignDHCPServer
        )
        return protocol, connecting

    def test_is_called_every_interval(self):
        clock = Clock()
        service = DHCPProbeService(sentinel.service, clock)

        # Avoid actually probing
        probe_dhcp = self.patch(service, "probe_dhcp")

        # Until the service has started, periodicprobe_dhcp() won't
        # be called.
        probe_dhcp.assert_not_called()

        # The first call is issued at startup.
        service.startService()
        probe_dhcp.assert_called_once_with()

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)

        # No more periodic calls made.
        self.assertEqual(1, probe_dhcp.call_count)

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertEqual(2, probe_dhcp.call_count)

    @inlineCallbacks
    def test_exits_gracefully_if_cant_report_foreign_dhcp_server(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
                "links": [{"address": "10.0.0.1/24"}],
            }
        }

        maaslog = self.patch(dhcp_probe_service, "maaslog")
        deferToThread = self.patch(dhcp_probe_service, "deferToThread")
        deferToThread.side_effect = [defer.succeed(interfaces)]
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        probe_interface.return_value = ["192.168.0.100"]
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        del protocol._commandDispatch[
            region.ReportForeignDHCPServer.commandName
        ]

        rpc_service = Mock()
        rpc_service.getClientNow.return_value = defer.succeed(
            getRegionClient()
        )
        service = DHCPProbeService(rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        maaslog.error.assert_called_once_with(
            "Unable to inform region of DHCP server: the region "
            "does not yet support the ReportForeignDHCPServer RPC "
            "method."
        )

    def test_logs_errors(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
                "links": [{"address": "10.0.0.1/24"}],
            }
        }

        maaslog = self.patch(dhcp_probe_service, "maaslog")
        mock_interfaces = self.patch(
            dhcp_probe_service, "get_all_interfaces_definition"
        )
        mock_interfaces.return_value = interfaces
        service = DHCPProbeService(sentinel.service, clock)
        error_message = factory.make_string()
        self.patch(service, "probe_dhcp").side_effect = Exception(
            error_message
        )
        with TwistedLoggerFixture() as logger:
            service.startService()
        maaslog.error.assert_called_once_with(
            "Unable to probe for DHCP servers: %s", error_message
        )
        self.assertIn("Running periodic DHCP probe.", logger.messages)
        self.assertIn("Unable to probe for DHCP servers.", logger.messages)

    @inlineCallbacks
    def test_skips_disabled_interfaces(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": False,
                "links": [{"address": "10.0.0.1/24"}],
            }
        }
        mock_interfaces = self.patch(
            dhcp_probe_service, "get_all_interfaces_definition"
        )
        mock_interfaces.return_value = interfaces
        service = DHCPProbeService(sentinel.service, clock)
        try_get_client = self.patch(service, "_tryGetClient")
        try_get_client.getClientNow = Mock()
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        yield service.startService()
        yield service.stopService()
        probe_interface.assert_not_called()

    @inlineCallbacks
    def test_probes_ipv4_interfaces(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
                "links": [{"address": "10.0.0.1/24"}],
            }
        }
        mock_interfaces = self.patch(
            dhcp_probe_service, "get_all_interfaces_definition"
        )
        mock_interfaces.return_value = interfaces
        service = DHCPProbeService(sentinel.service, clock)
        try_get_client = self.patch(service, "_tryGetClient")
        try_get_client.getClientNow = Mock()
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        yield service.startService()
        yield service.stopService()
        probe_interface.assert_called_once()

    @inlineCallbacks
    def test_skips_ipv6_interfaces(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
                "links": [{"address": "2001:db8::1/64"}],
            }
        }
        mock_interfaces = self.patch(
            dhcp_probe_service, "get_all_interfaces_definition"
        )
        mock_interfaces.return_value = interfaces
        service = DHCPProbeService(sentinel.service, clock)
        try_get_client = self.patch(service, "_tryGetClient")
        try_get_client.getClientNow = Mock()
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        yield service.startService()
        yield service.stopService()
        probe_interface.assert_not_called()

    @inlineCallbacks
    def test_skips_unconfigured_interfaces(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {interface_name: {"enabled": True, "links": []}}
        mock_interfaces = self.patch(
            dhcp_probe_service, "get_all_interfaces_definition"
        )
        mock_interfaces.return_value = interfaces
        service = DHCPProbeService(sentinel.service, clock)
        try_get_client = self.patch(service, "_tryGetClient")
        try_get_client.getClientNow = Mock()
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        yield service.startService()
        yield service.stopService()
        probe_interface.assert_not_called()

    @inlineCallbacks
    def test_reports_foreign_dhcp_servers_to_region(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
                "links": [{"address": "10.0.0.1/24"}],
            }
        }

        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        deferToThread = self.patch(dhcp_probe_service, "deferToThread")
        foreign_dhcp_ip = factory.make_ipv4_address()
        deferToThread.side_effect = [defer.succeed(interfaces)]
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        probe_interface.return_value = [foreign_dhcp_ip]
        client = getRegionClient()
        rpc_service = Mock()
        rpc_service.getClientNow.return_value = defer.succeed(client)

        service = DHCPProbeService(rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        protocol.ReportForeignDHCPServer.assert_called_once_with(
            protocol,
            system_id=client.localIdent,
            interface_name=interface_name,
            dhcp_ip=foreign_dhcp_ip,
        )

    @inlineCallbacks
    def test_reports_lack_of_foreign_dhcp_servers_to_region(self):
        clock = Clock()
        interface_name = factory.make_name("eth")
        interfaces = {
            interface_name: {
                "enabled": True,
                "links": [{"address": "10.0.0.1/24"}],
            }
        }

        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        deferToThread = self.patch(dhcp_probe_service, "deferToThread")
        deferToThread.side_effect = [defer.succeed(interfaces)]
        probe_interface = self.patch(dhcp_probe_service, "probe_interface")
        probe_interface.return_value = []

        client = getRegionClient()
        rpc_service = Mock()
        rpc_service.getClientNow.return_value = defer.succeed(client)
        service = DHCPProbeService(rpc_service, clock)
        yield service.startService()
        yield service.stopService()

        protocol.ReportForeignDHCPServer.assert_called_once_with(
            protocol,
            system_id=client.localIdent,
            interface_name=interface_name,
            dhcp_ip=None,
        )
