# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.dli`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import dli as dli_module
from provisioningserver.utils.shell import has_command_available


class TestDLIPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = dli_module.DLIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["wget"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = dli_module.DLIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test_power_on(self):
        driver = dli_module.DLIPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_on, "fake_id")

    def test_power_off(self):
        driver = dli_module.DLIPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_off, "fake_id")

    def test_power_query(self):
        driver = dli_module.DLIPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_query, "fake_id")
