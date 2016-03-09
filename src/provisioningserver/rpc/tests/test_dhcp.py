# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.dhcp`."""

__all__ = []

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockCalledWith,
    MockNotCalled,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import ANY
from provisioningserver.dhcp.testing.config import (
    make_failover_peer_config,
    make_host,
    make_interface,
    make_shared_network,
)
from provisioningserver.rpc import (
    dhcp,
    exceptions,
)
from provisioningserver.utils.service_monitor import ServiceActionError
from provisioningserver.utils.shell import ExternalProcessError
from testtools import ExpectedException
from twisted.internet.defer import inlineCallbacks


class TestConfigureDHCP(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("DHCPv4", {"server": dhcp.DHCPv4Server}),
        ("DHCPv6", {"server": dhcp.DHCPv6Server}),
    )

    def configure(
            self, omapi_key, failover_peers, shared_networks,
            hosts, interfaces):
        server = self.server(omapi_key)
        return dhcp.configure(
            server, failover_peers, shared_networks, hosts, interfaces)

    def patch_os_exists(self):
        return self.patch_autospec(dhcp.os.path, "exists")

    def patch_sudo_delete_file(self):
        return self.patch_autospec(dhcp, 'sudo_delete_file')

    def patch_sudo_write_file(self):
        return self.patch_autospec(dhcp, 'sudo_write_file')

    def patch_restartService(self):
        return self.patch(dhcp.service_monitor, 'restartService')

    def patch_ensureService(self):
        return self.patch(dhcp.service_monitor, 'ensureService')

    def patch_get_config(self):
        return self.patch_autospec(dhcp, 'get_config')

    @inlineCallbacks
    def test__extracts_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restartService()
        failover_peers = [make_failover_peer_config() for _ in range(3)]
        shared_networks = [make_shared_network() for _ in range(3)]
        hosts = [make_host() for _ in range(3)]
        interfaces_names = [
            factory.make_name("eth")
            for _ in range(3)
        ]
        interfaces = [
            make_interface(name=name)
            for name in interfaces_names
        ]
        yield self.configure(
            factory.make_name('key'), failover_peers, shared_networks,
            hosts, interfaces)
        expected_interfaces = ' '.join(sorted(interfaces_names))
        self.assertThat(
            write_file,
            MockCalledWith(
                ANY,
                expected_interfaces.encode("utf-8")))

    @inlineCallbacks
    def test__composes_dhcp_config(self):
        self.patch_sudo_write_file()
        self.patch_restartService()
        get_config = self.patch_get_config()
        omapi_key = factory.make_name('key')
        failover_peer = make_failover_peer_config()
        shared_network = make_shared_network()
        host = make_host()
        interface = make_interface()
        yield self.configure(
            omapi_key, [failover_peer], [shared_network], [host], [interface])
        self.assertThat(
            get_config,
            MockCalledOnceWith(
                self.server.template_basename, omapi_key=omapi_key,
                failover_peers=[failover_peer],
                shared_networks=[shared_network],
                hosts=[host]))

    @inlineCallbacks
    def test__writes_dhcp_config(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restartService()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        host = make_host()
        interface = make_interface()
        expected_config = factory.make_name('config')
        self.patch_get_config().return_value = expected_config

        yield self.configure(
            factory.make_name('key'),
            [failover_peers], [shared_network], [host], [interface])

        self.assertThat(
            write_file,
            MockAnyCall(
                self.server.config_filename, expected_config.encode("utf-8")))

    @inlineCallbacks
    def test__writes_interfaces_file(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restartService()
        yield self.configure(
            factory.make_name('key'),
            [make_failover_peer_config()], [make_shared_network()],
            [make_host()], [make_interface()])
        self.assertThat(
            write_file,
            MockCalledWith(self.server.interfaces_filename, ANY))

    @inlineCallbacks
    def test__restarts_dhcp_server_if_subnets_defined(self):
        self.patch_sudo_write_file()
        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service)
        on = self.patch_autospec(dhcp_service, "on")
        restart_service = self.patch_restartService()
        yield self.configure(
            factory.make_name('key'),
            [make_failover_peer_config()], [make_shared_network()],
            [make_host()], [make_interface()])
        self.assertThat(on, MockCalledOnceWith())
        self.assertThat(
            restart_service, MockCalledOnceWith(self.server.dhcp_service))

    @inlineCallbacks
    def test__deletes_dhcp_config_if_no_subnets_defined(self):
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = True
        mock_sudo_delete = self.patch_sudo_delete_file()
        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service)
        self.patch_autospec(dhcp_service, "off")
        self.patch_restartService()
        self.patch_ensureService()
        yield self.configure(factory.make_name('key'), [], [], [], [])
        self.assertThat(
            mock_sudo_delete, MockCalledOnceWith(self.server.config_filename))

    @inlineCallbacks
    def test__stops_dhcp_server_if_no_subnets_defined(self):
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = False
        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service)
        off = self.patch_autospec(dhcp_service, "off")
        restart_service = self.patch_restartService()
        ensure_service = self.patch_ensureService()
        yield self.configure(factory.make_name('key'), [], [], [], [])
        self.assertThat(off, MockCalledOnceWith())
        self.assertThat(
            ensure_service, MockCalledOnceWith(self.server.dhcp_service))
        self.assertThat(restart_service, MockNotCalled())

    @inlineCallbacks
    def test__converts_failure_writing_file_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file().side_effect = (
            ExternalProcessError(1, "sudo something"))
        self.patch_restartService()
        with ExpectedException(exceptions.CannotConfigureDHCP):
            yield self.configure(
                factory.make_name('key'),
                [make_failover_peer_config()], [make_shared_network()],
                [make_host()], [make_interface()])

    @inlineCallbacks
    def test__converts_dhcp_restart_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_restartService().side_effect = ServiceActionError()
        with ExpectedException(exceptions.CannotConfigureDHCP):
            yield self.configure(
                factory.make_name('key'),
                [make_failover_peer_config()], [make_shared_network()],
                [make_host()], [make_interface()])

    @inlineCallbacks
    def test__converts_stop_dhcp_server_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_ensureService().side_effect = ServiceActionError()
        with ExpectedException(exceptions.CannotConfigureDHCP):
            yield self.configure(
                factory.make_name('key'), [], [], [], [])

    @inlineCallbacks
    def test__does_not_log_ServiceActionError(self):
        self.patch_sudo_write_file()
        self.patch_ensureService().side_effect = ServiceActionError()
        with FakeLogger("maas") as logger:
            with ExpectedException(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name('key'), [], [], [], [])
        self.assertDocTestMatches("", logger.output)

    @inlineCallbacks
    def test__does_log_other_exceptions(self):
        self.patch_sudo_write_file()
        self.patch_ensureService().side_effect = (
            factory.make_exception("DHCP is on strike today"))
        with FakeLogger("maas") as logger:
            with ExpectedException(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name('key'), [], [], [], [])
        self.assertDocTestMatches(
            "DHCPv... server failed to stop: DHCP is on strike today",
            logger.output)

    @inlineCallbacks
    def test__does_not_log_ServiceActionError_when_restarting(self):
        self.patch_sudo_write_file()
        self.patch_restartService().side_effect = ServiceActionError()
        with FakeLogger("maas") as logger:
            with ExpectedException(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name('key'),
                    [make_failover_peer_config()], [make_shared_network()],
                    [make_host()], [make_interface()])
        self.assertDocTestMatches("", logger.output)

    @inlineCallbacks
    def test__does_log_other_exceptions_when_restarting(self):
        self.patch_sudo_write_file()
        self.patch_restartService().side_effect = (
            factory.make_exception("DHCP is on strike today"))
        with FakeLogger("maas") as logger:
            with ExpectedException(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name('key'),
                    [make_failover_peer_config()], [make_shared_network()],
                    [make_host()], [make_interface()])
        self.assertDocTestMatches(
            "DHCPv... server failed to restart (for network interfaces ...): "
            "DHCP is on strike today", logger.output)
