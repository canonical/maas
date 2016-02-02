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
from maastesting.testcase import MAASTestCase
from mock import ANY
from provisioningserver.dhcp.testing.config import make_subnet_config
from provisioningserver.drivers.service import ServiceRegistry
from provisioningserver.rpc import (
    dhcp,
    exceptions,
)
from provisioningserver.service_monitor import ServiceActionError
from provisioningserver.utils.shell import ExternalProcessError


class TestConfigureDHCP(MAASTestCase):

    scenarios = (
        ("DHCPv4", {"server": dhcp.DHCPv4Server}),
        ("DHCPv6", {"server": dhcp.DHCPv6Server}),
    )

    def configure(self, omapi_key, subnets):
        server = self.server(omapi_key)
        dhcp.configure(server, subnets)

    def patch_os_exists(self):
        return self.patch_autospec(dhcp.os.path, "exists")

    def patch_sudo_delete_file(self):
        return self.patch_autospec(dhcp, 'sudo_delete_file')

    def patch_sudo_write_file(self):
        return self.patch_autospec(dhcp, 'sudo_write_file')

    def patch_restart_service(self):
        return self.patch(dhcp.service_monitor, 'restart_service')

    def patch_ensure_service(self):
        return self.patch(dhcp.service_monitor, 'ensure_service')

    def patch_get_config(self):
        return self.patch_autospec(dhcp, 'get_config')

    def test__extracts_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_service()
        subnets = [make_subnet_config() for _ in range(3)]
        self.configure(factory.make_name('key'), subnets)
        interfaces = ' '.join(
            sorted(subnet['interface'] for subnet in subnets))
        self.assertThat(
            write_file,
            MockCalledWith(
                ANY,
                interfaces.encode("utf-8")))

    def test__eliminates_duplicate_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_service()
        interface = factory.make_name('interface')
        subnets = [make_subnet_config() for _ in range(2)]
        for subnet in subnets:
            subnet['interface'] = interface
        self.configure(factory.make_name('key'), subnets)
        self.assertThat(
            write_file, MockCalledWith(ANY, interface.encode("utf-8")))

    def test__composes_dhcp_config(self):
        self.patch_sudo_write_file()
        self.patch_restart_service()
        get_config = self.patch_get_config()
        omapi_key = factory.make_name('key')
        subnet = make_subnet_config()
        self.configure(omapi_key, [subnet])
        self.assertThat(
            get_config,
            MockCalledOnceWith(
                self.server.template_basename, omapi_key=omapi_key,
                dhcp_subnets=[subnet]))

    def test__writes_dhcp_config(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_service()

        subnet = make_subnet_config()
        expected_config = factory.make_name('config')
        self.patch_get_config().return_value = expected_config

        self.configure(factory.make_name('key'), [subnet])

        self.assertThat(
            write_file,
            MockAnyCall(
                self.server.config_filename, expected_config.encode("utf-8")))

    def test__writes_interfaces_file(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_service()
        self.configure(factory.make_name('key'), [make_subnet_config()])
        self.assertThat(
            write_file,
            MockCalledWith(self.server.interfaces_filename, ANY))

    def test__restarts_dhcp_server_if_subnets_defined(self):
        self.patch_sudo_write_file()
        dhcp_service = ServiceRegistry[self.server.dhcp_service]
        on = self.patch_autospec(dhcp_service, "on")
        restart_service = self.patch_restart_service()
        self.configure(factory.make_name('key'), [make_subnet_config()])
        self.assertThat(on, MockCalledOnceWith())
        self.assertThat(
            restart_service, MockCalledOnceWith(self.server.dhcp_service))

    def test__deletes_dhcp_config_if_no_subnets_defined(self):
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = True
        mock_sudo_delete = self.patch_sudo_delete_file()
        dhcp_service = ServiceRegistry[self.server.dhcp_service]
        self.patch_autospec(dhcp_service, "off")
        self.patch_restart_service()
        self.patch_ensure_service()
        self.configure(factory.make_name('key'), [])
        self.assertThat(
            mock_sudo_delete, MockCalledOnceWith(self.server.config_filename))

    def test__stops_dhcp_server_if_no_subnets_defined(self):
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = False
        dhcp_service = ServiceRegistry[self.server.dhcp_service]
        off = self.patch_autospec(dhcp_service, "off")
        restart_service = self.patch_restart_service()
        ensure_service = self.patch_ensure_service()
        self.configure(factory.make_name('key'), [])
        self.assertThat(off, MockCalledOnceWith())
        self.assertThat(
            ensure_service, MockCalledOnceWith(self.server.dhcp_service))
        self.assertThat(restart_service, MockNotCalled())

    def test__converts_failure_writing_file_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file().side_effect = (
            ExternalProcessError(1, "sudo something"))
        self.patch_restart_service()
        self.assertRaises(
            exceptions.CannotConfigureDHCP, self.configure,
            factory.make_name('key'), [make_subnet_config()])

    def test__converts_dhcp_restart_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_restart_service().side_effect = ServiceActionError()
        self.assertRaises(
            exceptions.CannotConfigureDHCP, self.configure,
            factory.make_name('key'), [make_subnet_config()])

    def test__converts_stop_dhcp_server_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_ensure_service().side_effect = ServiceActionError()
        self.assertRaises(
            exceptions.CannotConfigureDHCP, self.configure,
            factory.make_name('key'), [])

    def test__does_not_log_ServiceActionError(self):
        self.patch_sudo_write_file()
        self.patch_ensure_service().side_effect = ServiceActionError()
        with FakeLogger("maas") as logger:
            self.assertRaises(
                exceptions.CannotConfigureDHCP, self.configure,
                factory.make_name('key'), [])
        self.assertDocTestMatches("", logger.output)

    def test__does_log_other_exceptions(self):
        self.patch_sudo_write_file()
        self.patch_ensure_service().side_effect = (
            factory.make_exception("DHCP is on strike today"))
        with FakeLogger("maas") as logger:
            self.assertRaises(
                exceptions.CannotConfigureDHCP, self.configure,
                factory.make_name('key'), [])
        self.assertDocTestMatches(
            "DHCPv... server failed to stop: DHCP is on strike today",
            logger.output)

    def test__does_not_log_ServiceActionError_when_restarting(self):
        self.patch_sudo_write_file()
        self.patch_restart_service().side_effect = ServiceActionError()
        with FakeLogger("maas") as logger:
            self.assertRaises(
                exceptions.CannotConfigureDHCP, self.configure,
                factory.make_name('key'), [make_subnet_config()])
        self.assertDocTestMatches("", logger.output)

    def test__does_log_other_exceptions_when_restarting(self):
        self.patch_sudo_write_file()
        self.patch_restart_service().side_effect = (
            factory.make_exception("DHCP is on strike today"))
        with FakeLogger("maas") as logger:
            self.assertRaises(
                exceptions.CannotConfigureDHCP, self.configure,
                factory.make_name('key'), [make_subnet_config()])
        self.assertDocTestMatches(
            "DHCPv... server failed to restart (for network interfaces ...): "
            "DHCP is on strike today", logger.output)
