# Copyright 2014 Canonical Ltd.  This software is licensed under the
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

from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import ANY
from provisioningserver.dhcp import control
from provisioningserver.dhcp.control import (
    call_service_script,
    restart_dhcpv4,
    restart_dhcpv6,
    stop_dhcpv4,
    stop_dhcpv6,
    )


def patch_call_and_check(testcase):
    """Patch `call_and_check`."""
    return testcase.patch(control, 'call_and_check')


class TestCallServiceScript(MAASTestCase):
    """Tests for `call_service_script`."""

    def test__fails_on_weird_IP_version(self):
        self.assertRaises(KeyError, call_service_script, 5, 'restart')

    def test__controls_maas_dhcp_server_for_IP_version_4(self):
        call_and_check = patch_call_and_check(self)
        call_service_script(4, 'stop')
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcp-server', 'stop'],
                env=ANY))

    def test__controls_maas_dhcpv6_server_for_IP_version_6(self):
        call_and_check = patch_call_and_check(self)
        call_service_script(6, 'stop')
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpv6-server', 'stop'],
                env=ANY))

    def test__sets_C_locale(self):
        call_and_check = patch_call_and_check(self)
        call_service_script(4, 'stop')
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(ANY, env={'LC_ALL': 'C'}))


class TestControl(MAASTestCase):

    def test_restart_dhcpv4(self):
        call_and_check = patch_call_and_check(self)
        restart_dhcpv4()
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcp-server', 'restart'],
                env={'LC_ALL': 'C'}))

    def test_restart_dhcpv6(self):
        call_and_check = patch_call_and_check(self)
        restart_dhcpv6()
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpv6-server', 'restart'],
                env={'LC_ALL': 'C'}))

    def test_stop_dhcpv4(self):
        call_and_check = patch_call_and_check(self)
        stop_dhcpv4()
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcp-server', 'stop'],
                env={'LC_ALL': 'C'}))

    def test_stop_dhcpv6(self):
        call_and_check = patch_call_and_check(self)
        stop_dhcpv6()
        self.assertThat(
            call_and_check,
            MockCalledOnceWith(
                ['sudo', '-n', 'service', 'maas-dhcpv6-server', 'stop'],
                env={'LC_ALL': 'C'}))
