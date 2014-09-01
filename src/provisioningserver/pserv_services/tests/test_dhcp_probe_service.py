# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for periodic DHCP prober."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from unittest import skip

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
from provisioningserver.pserv_services import dhcp_probe_service
from provisioningserver.pserv_services.dhcp_probe_service import (
    PeriodicDHCPProbeService,
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

    def setUp(self):
        super(TestDHCPProbeService, self).setUp()
        self.cluster_uuid = factory.make_UUID()

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.GetClusterInterfaces, region.ReportForeignDHCPServer)
        return protocol, connecting

    def test_is_called_every_interval(self):
        clock = Clock()
        service = PeriodicDHCPProbeService(
            sentinel.service, clock, self.cluster_uuid)

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
        interface = {
            'name': 'eth0',
            'ip': '192.168.1.1',
            }
        rpc_service = Mock()
        rpc_client = rpc_service.getClient.return_value
        rpc_client.side_effect = [
            defer.succeed(dict(interfaces=[interface])),
        ]

        # We could patch out 'periodic_probe_task' instead here but this
        # is better because:
        # 1. The former requires spinning the reactor again before being
        #    able to test the result.
        # 2. This way there's no thread to clean up after the test.
        deferToThread = self.patch(dhcp_probe_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        service = PeriodicDHCPProbeService(
            rpc_service, clock, self.cluster_uuid)
        service.startService()
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                dhcp_probe_service.probe_interface,
                interface['name'], interface['ip']))

    @skip("Temporarily broken, but Graham is on the way.")
    @defer.inlineCallbacks
    def test_exists_gracefully_if_cant_get_interfaces(self):
        clock = Clock()
        maaslog = self.patch(dhcp_probe_service, 'maaslog')
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        protocol.GetClusterInterfaces.side_effect = (
            dhcp_probe_service.NoSuchMethod())
        rpc_service = Mock()
        rpc_service.getClient.return_value = getRegionClient()
        service = PeriodicDHCPProbeService(
            rpc_service, clock, self.cluster_uuid)
        service.startService()

        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to query region for interfaces: Region does not "
                "support the GetClusterInterfaces RPC method."))

    @skip("Temporarily broken, but Graham is on the way.")
    @defer.inlineCallbacks
    def test_exists_gracefully_if_cant_report_foreign_dhcp_server(self):
        clock = Clock()
        maaslog = self.patch(dhcp_probe_service, 'maaslog')
        deferToThread = self.patch(
            dhcp_probe_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(['192.168.0.100'])
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        protocol.ReportForeignDHCPServer.side_effect = (
            dhcp_probe_service.NoSuchMethod())
        protocol.GetClusterInterfaces.return_value = {
            'interfaces': [
                {'name': 'eth0', 'ip': '192.168.0.1'},
            ]}

        rpc_service = Mock()
        rpc_service.getClient.return_value = getRegionClient()
        service = PeriodicDHCPProbeService(
            rpc_service, clock, self.cluster_uuid)
        service.startService()

        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to inform region of rogue DHCP server: the region "
                "does not yet support the ReportForeignDHCPServer RPC "
                "method."))

    def test_logs_errors(self):
        clock = Clock()
        maaslog = self.patch(dhcp_probe_service, 'maaslog')
        service = PeriodicDHCPProbeService(
            sentinel.service, clock, self.cluster_uuid)
        error_message = factory.make_string()
        self.patch(service, 'probe_dhcp').side_effect = Exception(
            error_message)
        service.startService()
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "Unable to probe for rogue DHCP servers: %s",
                error_message))

    @skip("Temporarily broken, but Graham is on the way.")
    @defer.inlineCallbacks
    def test_reports_foreign_dhcp_servers_to_region(self):
        clock = Clock()
        deferToThread = self.patch(
            dhcp_probe_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(['192.168.0.100'])
        protocol, connecting = self.patch_rpc_methods()
        self.addCleanup((yield connecting))

        interface = {'name': 'eth0', 'ip': '192.168.0.1'},
        protocol.GetClusterInterfaces.return_value = {
            'interfaces': [interface]}

        rpc_service = Mock()
        rpc_service.getClient.return_value = getRegionClient()
        service = PeriodicDHCPProbeService(
            rpc_service, clock, self.cluster_uuid)
        service.startService()

        self.assertThat(
            protocol.ReportForeignDHCPServer,
            MockCalledOnceWith(
                cluster_uuid=self.cluster_uuid, name=interface['name'],
                foreign_dhcp_ip='192.168.0.100'))
