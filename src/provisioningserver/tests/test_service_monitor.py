# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DHCPv4 and DHCPv6 service driver."""

__all__ = []

from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.rackdservices.testing import (
    prepareRegionForGetControllerType,
)
from provisioningserver.service_monitor import (
    DHCPService,
    DHCPv4Service,
    DHCPv6Service,
    NTPServiceOnRack,
    service_monitor,
)
from provisioningserver.utils.service_monitor import SERVICE_STATE
from testtools.matchers import Equals
from twisted.internet.defer import inlineCallbacks


class TestDHCPService(MAASTestCase):

    def make_dhcp_service(self):

        class FakeDHCPService(DHCPService):

            name = factory.make_name("name")
            service_name = factory.make_name("service")
            snap_service_name = factory.make_name("service")

        return FakeDHCPService()

    def test_expected_state_starts_off(self):
        service = self.make_dhcp_service()
        self.assertEqual(SERVICE_STATE.OFF, service.expected_state)

    def test_getExpectedState_returns_from_expected_state(self):
        service = self.make_dhcp_service()
        service.expected_state = sentinel.state
        self.assertEqual((sentinel.state, None), service.getExpectedState())

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


class TestNTPServiceOnRack(MAASTestCase):

    def test_name_and_service_name(self):
        ntp = NTPServiceOnRack()
        self.assertEqual("ntp", ntp.service_name)
        self.assertEqual("ntp_rack", ntp.name)


class TestNTPServiceOnRack_Scenarios(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    scenarios = (
        ("rack", dict(
            is_region=False, is_rack=True,
            expected_state=SERVICE_STATE.ON,
            expected_info=None,
        )),
        ("region", dict(
            is_region=True, is_rack=False,
            expected_state=SERVICE_STATE.ANY,
            expected_info=None,
        )),
        ("region+rack", dict(
            is_region=True, is_rack=True,
            expected_state=SERVICE_STATE.ANY,
            expected_info="managed by the region.",
        )),
        ("machine", dict(
            is_region=False, is_rack=False,
            expected_state=SERVICE_STATE.ANY,
            expected_info=None,
        )),
    )

    def setUp(self):
        super(TestNTPServiceOnRack_Scenarios, self).setUp()
        return prepareRegionForGetControllerType(
            self, is_region=self.is_region, is_rack=self.is_rack)

    @inlineCallbacks
    def test_getExpectedState(self):
        ntp = NTPServiceOnRack()
        self.assertThat(
            (yield ntp.getExpectedState()),
            Equals((self.expected_state, self.expected_info)))


class TestGlobalServiceMonitor(MAASTestCase):

    def test__includes_all_services(self):
        self.assertItemsEqual(
            ["dhcpd", "dhcpd6", "ntp_rack"],
            service_monitor._services.keys())
