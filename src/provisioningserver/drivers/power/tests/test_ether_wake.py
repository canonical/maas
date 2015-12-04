# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ether_wake`."""

__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import ether_wake as ether_wake_module
from provisioningserver.utils.shell import has_command_available


class TestEtherWakePowerDriver(MAASTestCase):

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = ether_wake_module.EtherWakePowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["wakeonlan or etherwake"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = ether_wake_module.EtherWakePowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test_power_on(self):
        driver = ether_wake_module.EtherWakePowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_on, "fake_id", {})

    def test_power_off(self):
        driver = ether_wake_module.EtherWakePowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_off, "fake_id", {})

    def test_power_query(self):
        driver = ether_wake_module.EtherWakePowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_query, "fake_id", {})
