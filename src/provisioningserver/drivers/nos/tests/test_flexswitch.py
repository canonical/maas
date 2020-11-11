# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.nos.flexswitch`."""


from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.nos import flexswitch as flexswitch_module


class TestFlexswitchNOSDriver(MAASTestCase):
    def test_is_switch_supported_not(self):
        driver = flexswitch_module.FlexswitchNOSDriver()
        self.assertFalse(driver.is_switch_supported("Foo", "bar-v1"))

    def test_is_switch_supported_wedge40(self):
        driver = flexswitch_module.FlexswitchNOSDriver()
        self.assertTrue(driver.is_switch_supported("accton", "wedge40"))

    def test_is_switch_supported_wedge100(self):
        driver = flexswitch_module.FlexswitchNOSDriver()
        self.assertTrue(driver.is_switch_supported("accton", "wedge100"))
