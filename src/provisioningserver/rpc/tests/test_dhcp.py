# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.dhcp`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    call,
    sentinel,
)
from provisioningserver.dhcp.omshell import Omshell
from provisioningserver.dhcp.testing.config import make_subnet_config
from provisioningserver.drivers.service import (
    SERVICE_STATE,
    ServiceRegistry,
)
from provisioningserver.drivers.service.dhcp import DHCPv4Service
from provisioningserver.rpc import (
    dhcp,
    exceptions,
)
from provisioningserver.rpc.exceptions import (
    CannotCreateHostMap,
    CannotRemoveHostMap,
)
from provisioningserver.service_monitor import ServiceActionError
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.testing import RegistryFixture
from testtools import ExpectedException


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
        return self.patch_autospec(dhcp.service_monitor, 'restart_service')

    def patch_ensure_service(self):
        return self.patch_autospec(dhcp.service_monitor, 'ensure_service')

    def patch_get_config(self):
        return self.patch_autospec(dhcp, 'get_config')

    def test__extracts_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_service()
        subnets = [make_subnet_config() for _ in range(3)]
        self.configure(factory.make_name('key'), subnets)
        self.assertThat(
            write_file,
            MockCalledWith(
                ANY,
                ' '.join(sorted(subnet['interface'] for subnet in subnets))))

    def test__eliminates_duplicate_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_service()
        interface = factory.make_name('interface')
        subnets = [make_subnet_config() for _ in range(2)]
        for subnet in subnets:
            subnet['interface'] = interface
        self.configure(factory.make_name('key'), subnets)
        self.assertThat(write_file, MockCalledWith(ANY, interface))

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
            MockAnyCall(self.server.config_filename, expected_config))

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


class TestEnsureDHCPv4IsAccessible(MAASTestCase):

    def setUp(self):
        super(TestEnsureDHCPv4IsAccessible, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def make_dhcpv4_service(self):
        service = DHCPv4Service()
        ServiceRegistry.register_item(service.name, service)
        return service

    def test__raises_exception_if_service_should_be_off(self):
        service = self.make_dhcpv4_service()
        service.off()
        exception_type = factory.make_exception_type()
        with ExpectedException(exception_type):
            dhcp._ensure_dhcpv4_is_accessible(exception_type)

    def test__does_nothing_if_service_already_on(self):
        service = self.make_dhcpv4_service()
        service.on()
        mock_get_state = self.patch_autospec(
            dhcp.service_monitor, "get_service_state")
        mock_get_state.return_value = SERVICE_STATE.ON
        mock_ensure_service = self.patch_autospec(
            dhcp.service_monitor, "ensure_service")
        dhcp._ensure_dhcpv4_is_accessible(factory.make_exception_type())
        self.assertThat(mock_ensure_service, MockNotCalled())

    def test__calls_try_connection_to_check_omshell(self):
        service = self.make_dhcpv4_service()
        service.on()
        mock_get_state = self.patch_autospec(
            dhcp.service_monitor, "get_service_state")
        mock_get_state.return_value = SERVICE_STATE.OFF
        mock_ensure_service = self.patch_autospec(
            dhcp.service_monitor, "ensure_service")
        mock_omshell = self.patch_autospec(dhcp, "Omshell")
        mock_try_connection = mock_omshell.return_value.try_connection
        mock_try_connection.return_value = True
        dhcp._ensure_dhcpv4_is_accessible(factory.make_exception_type())
        self.assertThat(mock_ensure_service, MockCalledOnceWith("dhcp4"))
        self.assertThat(mock_try_connection, MockCalledOnceWith())

    def test__calls_try_connection_three_times_to_check_omshell(self):
        service = self.make_dhcpv4_service()
        service.on()
        mock_get_state = self.patch_autospec(
            dhcp.service_monitor, "get_service_state")
        mock_get_state.return_value = SERVICE_STATE.OFF
        mock_ensure_service = self.patch_autospec(
            dhcp.service_monitor, "ensure_service")
        mock_omshell = self.patch_autospec(dhcp, "Omshell")
        self.patch_autospec(dhcp.time, "sleep")
        mock_try_connection = mock_omshell.return_value.try_connection
        mock_try_connection.return_value = False
        fake_exception_type = factory.make_exception_type()
        with ExpectedException(fake_exception_type):
            dhcp._ensure_dhcpv4_is_accessible(fake_exception_type)
        self.assertThat(mock_ensure_service, MockCalledOnceWith("dhcp4"))
        self.assertEquals(mock_try_connection.call_count, 3)

    def test__raises_exception_on_ServiceActionError(self):
        service = self.make_dhcpv4_service()
        service.on()
        mock_get_state = self.patch_autospec(
            dhcp.service_monitor, "get_service_state")
        mock_get_state.return_value = SERVICE_STATE.OFF
        mock_ensure_service = self.patch_autospec(
            dhcp.service_monitor, "ensure_service")
        mock_ensure_service.side_effect = ServiceActionError()
        exception_type = factory.make_exception_type()
        with ExpectedException(exception_type):
            dhcp._ensure_dhcpv4_is_accessible(exception_type)

    def test__raises_exception_on_other_exceptions(self):
        service = self.make_dhcpv4_service()
        service.on()
        mock_get_state = self.patch_autospec(
            dhcp.service_monitor, "get_service_state")
        mock_get_state.return_value = SERVICE_STATE.OFF
        mock_ensure_service = self.patch_autospec(
            dhcp.service_monitor, "ensure_service")
        mock_ensure_service.side_effect = factory.make_exception()
        exception_type = factory.make_exception_type()
        with ExpectedException(exception_type):
            dhcp._ensure_dhcpv4_is_accessible(exception_type)


class TestCreateHostMaps(MAASTestCase):

    def setUp(self):
        super(TestCreateHostMaps, self).setUp()
        # Patch _ensure_dhcpv4_is_accessible.
        self._ensure_dhcpv4_is_accessible = self.patch_autospec(
            dhcp, "_ensure_dhcpv4_is_accessible")

    def test_calls__ensure_dhcpv4_is_accessible(self):
        self.patch(dhcp, "Omshell")
        dhcp.create_host_maps([], sentinel.shared_key)
        self.assertThat(
            self._ensure_dhcpv4_is_accessible,
            MockCalledOnceWith(CannotCreateHostMap))

    def test_creates_omshell(self):
        omshell = self.patch(dhcp, "Omshell")
        dhcp.create_host_maps([], sentinel.shared_key)
        self.assertThat(omshell, MockCallsMatch(
            call(server_address=ANY, shared_key=sentinel.shared_key),
        ))

    def test_calls_omshell_create(self):
        omshell_create = self.patch(Omshell, "create")
        mappings = [
            {"ip_address": factory.make_ipv4_address(),
             "mac_address": factory.make_mac_address()}
            for _ in range(5)
        ]
        dhcp.create_host_maps(mappings, sentinel.shared_key)
        self.assertThat(omshell_create, MockCallsMatch(*(
            call(mapping["ip_address"], mapping["mac_address"])
            for mapping in mappings
        )))

    def test_raises_error_when_omshell_crashes(self):
        error_message = factory.make_name("error").encode("ascii")
        omshell_create = self.patch(Omshell, "create")
        omshell_create.side_effect = ExternalProcessError(
            returncode=2, cmd=("omshell",), output=error_message)
        ip_address = factory.make_ipv4_address()
        mac_address = factory.make_mac_address()
        mappings = [{"ip_address": ip_address, "mac_address": mac_address}]
        with FakeLogger("maas.dhcp") as logger:
            error = self.assertRaises(
                exceptions.CannotCreateHostMap, dhcp.create_host_maps,
                mappings, sentinel.shared_key)
        # The CannotCreateHostMap exception includes a message describing the
        # problematic mapping.
        self.assertDocTestMatches(
            "%s -> %s: ..." % (mac_address, ip_address),
            unicode(error))
        # A message is also written to the maas.dhcp logger that describes the
        # problematic mapping.
        self.assertDocTestMatches(
            "Could not create host map for ... with address ...: ...",
            logger.output)


class TestRemoveHostMaps(MAASTestCase):

    def setUp(self):
        super(TestRemoveHostMaps, self).setUp()
        self.patch(Omshell, "remove")
        self.patch(Omshell, "nullify_lease")
        # Patch _ensure_dhcpv4_is_accessible.
        self._ensure_dhcpv4_is_accessible = self.patch_autospec(
            dhcp, "_ensure_dhcpv4_is_accessible")

    def test_calls__ensure_dhcpv4_is_accessible(self):
        self.patch(dhcp, "Omshell")
        dhcp.remove_host_maps([], sentinel.shared_key)
        self.assertThat(
            self._ensure_dhcpv4_is_accessible,
            MockCalledOnceWith(CannotRemoveHostMap))

    def test_removes_omshell(self):
        omshell = self.patch(dhcp, "Omshell")
        dhcp.remove_host_maps([], sentinel.shared_key)
        self.assertThat(omshell, MockCallsMatch(
            call(server_address=ANY, shared_key=sentinel.shared_key),
        ))

    def test_calls_omshell_remove(self):
        ip_addresses = [factory.make_ipv4_address() for _ in range(5)]
        dhcp.remove_host_maps(ip_addresses, sentinel.shared_key)
        self.assertThat(Omshell.remove, MockCallsMatch(*(
            call(ip_address) for ip_address in ip_addresses
        )))

    def test_calls_omshell_nullify_lease(self):
        ip_addresses = [factory.make_ipv4_address() for _ in range(5)]
        dhcp.remove_host_maps(ip_addresses, sentinel.shared_key)
        self.assertThat(Omshell.nullify_lease, MockCallsMatch(*(
            call(ip_address) for ip_address in ip_addresses
        )))

    def test_raises_error_when_omshell_crashes(self):
        error_message = factory.make_name("error").encode("ascii")
        Omshell.remove.side_effect = ExternalProcessError(
            returncode=2, cmd=("omshell",), output=error_message)
        ip_address = factory.make_ipv4_address()
        with FakeLogger("maas.dhcp") as logger:
            error = self.assertRaises(
                exceptions.CannotRemoveHostMap, dhcp.remove_host_maps,
                [ip_address], sentinel.shared_key)
        # The CannotRemoveHostMap exception includes a message describing the
        # problematic mapping.
        self.assertDocTestMatches("%s: ..." % ip_address, unicode(error))
        # A message is also written to the maas.dhcp logger that describes the
        # problematic mapping.
        self.assertDocTestMatches(
            "Could not remove host map for ...: ...",
            logger.output)


class TestOmshellError(MAASTestCase):
    """Test omshell error reporting"""

    def setUp(self):
        super(TestOmshellError, self).setUp()
        # Patch _ensure_dhcpv4_is_accessible.
        self._ensure_dhcpv4_is_accessible = self.patch_autospec(
            dhcp, "_ensure_dhcpv4_is_accessible")
        self.patch(ExternalProcessError, '__unicode__', lambda x: 'Error')

        def raise_ExternalProcessError(*args, **kwargs):
            raise ExternalProcessError(*args, **kwargs)

        self.patch(Omshell, "remove", raise_ExternalProcessError)

    def test__raises_CannotRemoveHostMap_if_omshell_offline(self):
        """If the DHCP server is offline, report a specific message"""

        omapi_key = factory.make_name('omapi-key')
        ip_address = factory.make_ipv4_address()
        self.patch(ExternalProcessError, 'output_as_unicode', 'not connected.')

        self.assertRaises(CannotRemoveHostMap,
                          dhcp.remove_host_maps, [ip_address], omapi_key)

        try:
            dhcp.remove_host_maps([ip_address], omapi_key)
        except CannotRemoveHostMap as e:
            self.assertEqual(e.args[0],
                             "The DHCP server could not be reached.")

    def test__raises_CannotRemoveHostMap_if_omshell_error(self):
        """Raise a CannotRemoveHostMap if omshell returns an error"""

        omapi_key = factory.make_name('omapi-key')
        ip_address = factory.make_ipv4_address()
        self.patch(ExternalProcessError, 'output_as_unicode', 'error.')

        self.assertRaises(CannotRemoveHostMap,
                          dhcp.remove_host_maps, [ip_address], omapi_key)
