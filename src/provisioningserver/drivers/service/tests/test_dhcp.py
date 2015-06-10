# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DHCPv4 and DHCPv6 service driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.dhcp import (
    DHCPv4_CONFIG_FILE,
    DHCPv6_CONFIG_FILE,
    DISABLED_DHCP_SERVER,
)
from provisioningserver.drivers.service import SERVICE_STATE
from provisioningserver.drivers.service.dhcp import (
    DHCPService,
    DHCPv4Service,
    DHCPv6Service,
)
from provisioningserver.path import get_path


class TestDHCPService(MAASTestCase):

    def make_dhcp_service(self, fake_config_file=None):
        if fake_config_file is None:
            fake_config_file = factory.make_name("config_file")

        class FakeDHCPService(DHCPService):

            name = factory.make_name("name")
            service_name = factory.make_name("service")
            config_file = fake_config_file

        return FakeDHCPService()

    def test_get_expected_state_returns_from_expected_state(self):
        service = self.make_dhcp_service()
        service.expected_state = sentinel.state
        self.assertEqual(sentinel.state, service.get_expected_state())

    def test_is_on_returns_True_when_expected_state_on(self):
        service = self.make_dhcp_service()
        service.expected_state = SERVICE_STATE.ON
        self.assertTrue(
            service.is_on(),
            "Did not return true when expected_state was on.")

    def test_is_on_returns_False_when_expected_state_off(self):
        service = self.make_dhcp_service()
        service.expected_state = SERVICE_STATE.OFF
        self.assertFalse(
            service.is_on(),
            "Did not return false when expected_state was off.")

    def test_on_sets_expected_state_to_on(self):
        service = self.make_dhcp_service()
        service.expected_state = SERVICE_STATE.OFF
        service.on()
        self.assertEqual(SERVICE_STATE.ON, service.expected_state)

    def test_off_sets_expected_state_to_off(self):
        service = self.make_dhcp_service()
        service.expected_state = SERVICE_STATE.ON
        service.off()
        self.assertEqual(SERVICE_STATE.OFF, service.expected_state)

    def test__get_starting_expected_state_returns_off_if_doesnt_exist(self):
        service = self.make_dhcp_service()
        self.assertEqual(
            SERVICE_STATE.OFF, service._get_starting_expected_state())

    def test__get_starting_expected_state_returns_on_if_not_disabled_cfg(self):
        service = self.make_dhcp_service()
        service.config_file = self.make_file()
        self.assertEqual(
            SERVICE_STATE.ON, service._get_starting_expected_state())

    def test__get_starting_expected_state_returns_off_if_disabled_cfg(self):
        service = self.make_dhcp_service()
        service.config_file = self.make_file(contents=DISABLED_DHCP_SERVER)
        self.assertEqual(
            SERVICE_STATE.OFF, service._get_starting_expected_state())


class TestDHCPv4Service(MAASTestCase):

    def test_service_name(self):
        service = DHCPv4Service()
        self.assertEqual("maas-dhcpd", service.service_name)

    def test_config_file(self):
        service = DHCPv4Service()
        self.assertEqual(get_path(DHCPv4_CONFIG_FILE), service.config_file)


class TestDHCPv6Service(MAASTestCase):

    def test_service_name(self):
        service = DHCPv6Service()
        self.assertEqual("maas-dhcpd6", service.service_name)

    def test_config_file(self):
        service = DHCPv6Service()
        self.assertEqual(get_path(DHCPv6_CONFIG_FILE), service.config_file)
