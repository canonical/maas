# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP control functions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import ANY
from provisioningserver.dhcp import control
from provisioningserver.dhcp.control import (
    call_service_script,
    restart_dhcpv4,
    restart_dhcpv6,
    stop_dhcp_server,
    stop_dhcpv4,
    stop_dhcpv6,
)
from provisioningserver.utils.shell import ExternalProcessError


def patch_call_and_check(testcase):
    """Patch `call_and_check`."""
    return testcase.patch(control, 'call_and_check')


def patch_call_service_script(testcase):
    """Patch `call_service_script`."""
    return testcase.patch(control, 'call_service_script')


class TestCallServiceScript(MAASTestCase):
    """Tests for `call_service_script`."""

    def test__fails_on_weird_IP_version(self):
        self.assertRaises(KeyError, call_service_script, 5, 'restart')

    def test__skips_call_and_check_when_in_develop_mode(self):
        self.patch(control, 'in_develop_mode').return_value = True
        call_and_check = patch_call_and_check(self)
        call_service_script(4, 'stop')
        self.assertThat(
            call_and_check,
            MockNotCalled())

    def test__controls_maas_dhcp_server_for_IP_version_4(self):
        call_and_check = patch_call_and_check(self)
        call_service_script(4, 'stop')
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpd', 'stop'],
                env=ANY))

    def test__controls_maas_dhcpv6_server_for_IP_version_6(self):
        call_and_check = patch_call_and_check(self)
        call_service_script(6, 'stop')
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpd6', 'stop'],
                env=ANY))

    def test__sets_C_locale(self):
        call_and_check = patch_call_and_check(self)
        call_service_script(4, 'stop')
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(ANY, env={'LC_ALL': 'C'}))


class TestStopDHCPServer(MAASTestCase):
    """Tests for `stop_dhcp_server`."""

    def test__stops_dhcpv4(self):
        call_and_check = patch_call_and_check(self)
        stop_dhcp_server(4)
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpd', 'stop'],
                env=ANY))

    def test__stops_dhcpv6(self):
        call_and_check = patch_call_and_check(self)
        stop_dhcp_server(6)
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpd6', 'stop'],
                env=ANY))

    def test__treats_already_stopped_as_success(self):
        patch_call_and_check(self).side_effect = ExternalProcessError(
            1, [factory.make_name('command')], "stop: Unknown instance:")
        # The error does not propagate out of stop_dhcp_server.
        self.assertIsNone(stop_dhcp_server(4))

    def test__propagates_other_failures(self):
        patch_call_and_check(self).side_effect = ExternalProcessError(
            1, [factory.make_name('command')], "stop: I don't feel like it.")
        self.assertRaises(ExternalProcessError, stop_dhcp_server, 4)


class TestControl(MAASTestCase):

    def test_restart_dhcpv4(self):
        call_and_check = patch_call_and_check(self)
        restart_dhcpv4()
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpd', 'restart'],
                env={'LC_ALL': 'C'}))

    def test_restart_dhcpv6(self):
        call_and_check = patch_call_and_check(self)
        restart_dhcpv6()
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpd6', 'restart'],
                env={'LC_ALL': 'C'}))

    def test_stop_dhcpv4(self):
        call_service_script = patch_call_service_script(self)
        stop_dhcpv4()
        self.assertThat(call_service_script, MockCalledOnceWith(4, 'stop'))

    def test_stop_dhcpv6(self):
        call_service_script = patch_call_service_script(self)
        stop_dhcpv6()
        self.assertThat(call_service_script, MockCalledOnceWith(6, 'stop'))
