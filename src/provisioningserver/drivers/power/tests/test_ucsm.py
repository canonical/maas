# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ucsm`."""

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import ucsm as ucsm_module
from provisioningserver.drivers.power.ucsm import (
    extract_ucsm_parameters,
    UCSMPowerDriver,
)


class TestUCSMPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = ucsm_module.UCSMPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name("system_id")
        url = factory.make_name("power_address")
        username = factory.make_name("power_user")
        password = factory.make_name("power_pass")
        uuid = factory.make_UUID()
        context = {
            "system_id": system_id,
            "power_address": url,
            "power_user": username,
            "power_pass": password,
            "uuid": uuid,
        }
        return system_id, url, username, password, uuid, context

    def test_extract_ucsm_parameters_extracts_parameters(self):
        (
            system_id,
            url,
            username,
            password,
            uuid,
            context,
        ) = self.make_parameters()

        self.assertEqual(
            (url, username, password, uuid), extract_ucsm_parameters(context)
        )

    def test_power_on_calls_power_control_ucsm(self):
        (
            system_id,
            url,
            username,
            password,
            uuid,
            context,
        ) = self.make_parameters()
        ucsm_power_driver = UCSMPowerDriver()
        power_control_ucsm = self.patch(ucsm_module, "power_control_ucsm")
        ucsm_power_driver.power_on(system_id, context)

        power_control_ucsm.assert_called_once_with(
            url, username, password, uuid, maas_power_mode="on"
        )

    def test_power_off_calls_power_control_ucsm(self):
        (
            system_id,
            url,
            username,
            password,
            uuid,
            context,
        ) = self.make_parameters()
        ucsm_power_driver = UCSMPowerDriver()
        power_control_ucsm = self.patch(ucsm_module, "power_control_ucsm")
        ucsm_power_driver.power_off(system_id, context)

        power_control_ucsm.assert_called_once_with(
            url, username, password, uuid, maas_power_mode="off"
        )

    def test_power_query_calls_power_state_ucsm(self):
        (
            system_id,
            url,
            username,
            password,
            uuid,
            context,
        ) = self.make_parameters()
        ucsm_power_driver = UCSMPowerDriver()
        power_state_ucsm = self.patch(ucsm_module, "power_state_ucsm")
        power_state_ucsm.return_value = "off"
        expected_result = ucsm_power_driver.power_query(system_id, context)

        power_state_ucsm.assert_called_once_with(url, username, password, uuid)
        self.assertEqual(expected_result, "off")
