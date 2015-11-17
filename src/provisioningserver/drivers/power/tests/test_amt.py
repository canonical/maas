# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.amt`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import amt as amt_module
from provisioningserver.utils.shell import has_command_available


class TestAMTPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = amt_module.AMTPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["amtterm", "wsmancli"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = amt_module.AMTPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test_power_on(self):
        driver = amt_module.AMTPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_on, "fake_id", {})

    def test_power_off(self):
        driver = amt_module.AMTPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_off, "fake_id", {})

    def test_power_query(self):
        driver = amt_module.AMTPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_query, "fake_id", {})
