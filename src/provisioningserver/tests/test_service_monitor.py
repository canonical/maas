# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DHCPv4 and DHCPv6 service driver."""

__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.service_monitor import (
    DHCPService,
    DHCPv4Service,
    DHCPv6Service,
    service_monitor,
    TGTService,
)
from provisioningserver.utils.service_monitor import SERVICE_STATE


class TestDHCPService(MAASTestCase):

    def make_dhcp_service(self):

        class FakeDHCPService(DHCPService):

            name = factory.make_name("name")
            service_name = factory.make_name("service")

        return FakeDHCPService()

    def test_expected_state_starts_off(self):
        service = self.make_dhcp_service()
        self.assertEqual(SERVICE_STATE.OFF, service.expected_state)

    def test_get_expected_state_returns_from_expected_state(self):
        service = self.make_dhcp_service()
        service.expected_state = sentinel.state
        self.assertEqual((sentinel.state, None), service.get_expected_state())

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


class TestDHCPv4Service(MAASTestCase):

    def test_name(self):
        service = DHCPv4Service()
        self.assertEqual("dhcpd", service.name)

    def test_service_name(self):
        service = DHCPv4Service()
        self.assertEqual("maas-dhcpd", service.service_name)


class TestDHCPv6Service(MAASTestCase):

    def test_name(self):
        service = DHCPv6Service()
        self.assertEqual("dhcpd6", service.name)

    def test_service_name(self):
        service = DHCPv6Service()
        self.assertEqual("maas-dhcpd6", service.service_name)


class TestTGTService(MAASTestCase):

    def test_service_name(self):
        tgt = TGTService()
        self.assertEqual("tgt", tgt.service_name)

    def test_get_expected_state(self):
        tgt = TGTService()
        self.assertEqual((SERVICE_STATE.ON, None), tgt.get_expected_state())


class TestGlobalServiceMonitor(MAASTestCase):

    def test__includes_all_services(self):
        self.assertItemsEqual(
            ["dhcpd", "dhcpd6", "tgt"], service_monitor._services.keys())
