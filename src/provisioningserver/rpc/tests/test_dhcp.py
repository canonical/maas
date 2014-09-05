# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from random import randint

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
from provisioningserver.dhcp import control
from provisioningserver.dhcp.omshell import Omshell
from provisioningserver.dhcp.testing.config import make_subnet_config
from provisioningserver.rpc import (
    dhcp,
    exceptions,
    )
from provisioningserver.rpc.exceptions import (
    CannotConfigureDHCP,
    CannotStopDHCP,
    )
from provisioningserver.utils.shell import ExternalProcessError


class TestConfigureDHCPv6(MAASTestCase):

    def patch_sudo_write_file(self):
        return self.patch(dhcp, 'sudo_write_file')

    def patch_restart_dhcpv6(self):
        return self.patch(control, 'restart_dhcpv6')

    def patch_get_config(self):
        return self.patch(dhcp, 'get_config')

    def test__extracts_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_dhcpv6()
        subnets = [make_subnet_config() for _ in range(3)]
        dhcp.configure_dhcpv6(factory.make_name('key'), subnets)
        self.assertThat(
            write_file,
            MockCalledWith(
                ANY,
                ' '.join(sorted(subnet['interface'] for subnet in subnets))))

    def test__eliminates_duplicate_interfaces(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_dhcpv6()
        interface = factory.make_name('interface')
        subnets = [make_subnet_config() for _ in range(2)]
        for subnet in subnets:
            subnet['interface'] = interface
        dhcp.configure_dhcpv6(factory.make_name('key'), subnets)
        self.assertThat(write_file, MockCalledWith(ANY, interface))

    def test__composes_dhcpv6_config(self):
        self.patch_sudo_write_file()
        self.patch_restart_dhcpv6()
        get_config = self.patch_get_config()
        omapi_key = factory.make_name('key')
        subnet = make_subnet_config()
        dhcp.configure_dhcpv6(omapi_key, [subnet])
        self.assertThat(
            get_config,
            MockCalledOnceWith(
                'dhcpd6.conf.template', omapi_key=omapi_key,
                dhcp_subnets=[subnet]))

    def test__writes_dhcpv6_config(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_dhcpv6()

        subnet = make_subnet_config()
        expected_config = factory.make_name('config')
        self.patch_get_config().return_value = expected_config

        dhcp.configure_dhcpv6(factory.make_name('key'), [subnet])

        self.assertThat(
            write_file,
            MockAnyCall(dhcp.DHCPv6_CONFIG_FILE, expected_config))

    def test__writes_interfaces_file(self):
        write_file = self.patch_sudo_write_file()
        self.patch_restart_dhcpv6()
        dhcp.configure_dhcpv6(factory.make_name('key'), [make_subnet_config()])
        self.assertThat(
            write_file,
            MockCalledWith(dhcp.DHCPv6_INTERFACES_FILE, ANY))

    def test__restarts_dhcpv6_server_if_subnets_defined(self):
        self.patch_sudo_write_file()
        restart_dhcpv6 = self.patch_restart_dhcpv6()
        dhcp.configure_dhcpv6(factory.make_name('key'), [make_subnet_config()])
        self.assertThat(restart_dhcpv6, MockCalledWith())

    def test__stops_dhcpv6_server_if_no_subnets_defined(self):
        self.patch_sudo_write_file()
        restart_dhcpv6 = self.patch_restart_dhcpv6()
        stop_dhcpv6 = self.patch(control, 'stop_dhcpv6')
        dhcp.configure_dhcpv6(factory.make_name('key'), [])
        self.assertThat(stop_dhcpv6, MockCalledWith())
        self.assertThat(restart_dhcpv6, MockNotCalled())

    def test__converts_failure_writing_file_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file().side_effect = (
            ExternalProcessError(1, "sudo something"))
        self.patch_restart_dhcpv6()
        self.assertRaises(
            exceptions.CannotConfigureDHCP,
            dhcp.configure_dhcpv6,
            factory.make_name('key'), [make_subnet_config()])

    def test__converts_dhcp_restart_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_restart_dhcpv6().side_effect = (
            ExternalProcessError(1, "sudo something"))
        self.assertRaises(
            exceptions.CannotConfigureDHCP,
            dhcp.configure_dhcpv6,
            factory.make_name('key'), [make_subnet_config()])


class TestCreateHostMaps(MAASTestCase):

    def test_creates_omshell(self):
        omshell = self.patch(dhcp, "Omshell")
        dhcp.create_host_maps([], sentinel.shared_key)
        self.assertThat(omshell, MockCallsMatch(
            call(server_address=ANY, shared_key=sentinel.shared_key),
        ))

    def test_calls_omshell_create(self):
        omshell_create = self.patch(Omshell, "create")
        mappings = [
            {"ip_address": factory.getRandomIPAddress(),
             "mac_address": factory.getRandomMACAddress()}
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
        ip_address = factory.getRandomIPAddress()
        mac_address = factory.getRandomMACAddress()
        mappings = [{"ip_address": ip_address, "mac_address": mac_address}]
        with FakeLogger("maas.dhcp") as logger:
            error = self.assertRaises(
                exceptions.CannotCreateHostMap, dhcp.create_host_maps,
                mappings, sentinel.shared_key)
        # The CannotCreateHostMap exception includes a message describing the
        # problematic mapping.
        self.assertDocTestMatches(
            "%s \u2192 %s: ..." % (mac_address, ip_address),
            unicode(error))
        # A message is also written to the maas.dhcp logger that describes the
        # problematic mapping.
        self.assertDocTestMatches(
            "Could not create host map for ... with address ...: ...",
            logger.output)


class TestRemoveHostMaps(MAASTestCase):

    def test_removes_omshell(self):
        omshell = self.patch(dhcp, "Omshell")
        dhcp.remove_host_maps([], sentinel.shared_key)
        self.assertThat(omshell, MockCallsMatch(
            call(server_address=ANY, shared_key=sentinel.shared_key),
        ))

    def test_calls_omshell_remove(self):
        omshell_remove = self.patch(Omshell, "remove")
        ip_addresses = [factory.getRandomIPAddress() for _ in range(5)]
        dhcp.remove_host_maps(ip_addresses, sentinel.shared_key)
        self.assertThat(omshell_remove, MockCallsMatch(*(
            call(ip_address) for ip_address in ip_addresses
        )))

    def test_raises_error_when_omshell_crashes(self):
        error_message = factory.make_name("error").encode("ascii")
        omshell_remove = self.patch(Omshell, "remove")
        omshell_remove.side_effect = ExternalProcessError(
            returncode=2, cmd=("omshell",), output=error_message)
        ip_address = factory.getRandomIPAddress()
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


class TestStopAndDisableDHCP(MAASTestCase):
    """Test `stop_and_disable_dhcpv4` and `stop_and_disable_dhcpv6`."""

    scenarios = (
        ("DHCPv4", {
            "stop_dhcp": (control, "stop_dhcpv4"),  # For patching.
            "stop_and_disable_dhcp": dhcp.stop_and_disable_dhcpv4,
            "expected_config_file": dhcp.DHCPv4_CONFIG_FILE,
        }),
        ("DHCPv6", {
            "stop_dhcp": (control, "stop_dhcpv6"),  # For patching.
            "stop_and_disable_dhcp": dhcp.stop_and_disable_dhcpv6,
            "expected_config_file": dhcp.DHCPv6_CONFIG_FILE,
        }),
    )

    def test__writes_config_and_stops_dhcp_server(self):
        # Avoid trying to actually write a file via sudo.
        sudo_write_file = self.patch_autospec(dhcp, "sudo_write_file")
        # Avoid trying to actually stop a live DHCP server.
        stop_dhcp = self.patch_autospec(*self.stop_dhcp)

        self.stop_and_disable_dhcp()

        self.assertThat(sudo_write_file, MockCalledOnceWith(
            self.expected_config_file, dhcp.DISABLED_DHCP_SERVER))
        self.assertThat(stop_dhcp, MockCalledOnceWith())

    def test__raises_CannotConfigureDHCP_when_config_file_write_fails(self):
        # Avoid trying to actually write a file via sudo.
        sudo_write_file = self.patch_autospec(dhcp, "sudo_write_file")
        # Avoid trying to actually stop a live DHCP server.
        stop_dhcp = self.patch_autospec(*self.stop_dhcp)

        # Simulate a failure when writing the configuration file.
        sudo_write_file.side_effect = ExternalProcessError(
            randint(1, 99), [factory.make_name("command")],
            factory.make_name("stderr"))

        self.assertRaises(CannotConfigureDHCP, self.stop_and_disable_dhcp)

        self.assertThat(sudo_write_file, MockCalledOnceWith(
            self.expected_config_file, dhcp.DISABLED_DHCP_SERVER))
        self.assertThat(stop_dhcp, MockNotCalled())

    def test__raises_CannotStopDHCP_when_stop_fails(self):
        # Avoid trying to actually write a file via sudo.
        sudo_write_file = self.patch_autospec(dhcp, "sudo_write_file")
        # Avoid trying to actually stop a live DHCP server.
        stop_dhcp = self.patch_autospec(*self.stop_dhcp)

        # Simulate a failure when stopping the DHCP server.
        stop_dhcp.side_effect = ExternalProcessError(
            randint(1, 99), [factory.make_name("command")],
            factory.make_name("stderr"))

        self.assertRaises(CannotStopDHCP, self.stop_and_disable_dhcp)

        self.assertThat(sudo_write_file, MockCalledOnceWith(
            self.expected_config_file, dhcp.DISABLED_DHCP_SERVER))
        self.assertThat(stop_dhcp, MockCalledOnceWith())
