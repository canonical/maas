# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.fence_cdu`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import fence_cdu as fence_cdu_module
from provisioningserver.utils.shell import has_command_available


class TestFenceCDUPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = fence_cdu_module.FenceCDUPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["fence-agents"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = fence_cdu_module.FenceCDUPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test_power_on(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_on, "fake_id")

    def test_power_off(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_off, "fake_id")

    def test_power_query(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        self.assertRaises(
            NotImplementedError, driver.power_query, "fake_id")
