# Copyright 2015-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.seamicro`."""

from random import choice

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import PowerActionError
from provisioningserver.drivers.power import seamicro as seamicro_module
from provisioningserver.drivers.power.seamicro import (
    extract_seamicro_parameters,
    SeaMicroPowerDriver,
)
from provisioningserver.utils.shell import (
    ExternalProcessError,
    has_command_available,
)


class TestSeaMicroPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = seamicro_module.SeaMicroPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["ipmitool"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = seamicro_module.SeaMicroPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def make_context(self):
        ip = factory.make_name("power_address")
        username = factory.make_name("power_user")
        password = factory.make_name("power_pass")
        server_id = factory.make_name("system_id")
        context = {
            "power_address": ip,
            "power_user": username,
            "power_pass": password,
            "system_id": server_id,
        }
        return ip, username, password, server_id, context

    def test_extract_seamicro_parameters_extracts_parameters(self):
        ip, username, password, server_id, context = self.make_context()
        power_control = choice(["ipmi", "restapi", "restapi2"])
        context["power_control"] = power_control

        self.assertEqual(
            (ip, username, password, server_id, power_control),
            extract_seamicro_parameters(context),
        )

    def test_power_control_seamicro15k_ipmi_calls_call_and_check(self):
        ip, username, password, server_id, _ = self.make_context()
        power_change = choice(["on", "off"])
        seamicro_power_driver = SeaMicroPowerDriver()
        call_and_check_mock = self.patch(seamicro_module, "call_and_check")
        seamicro_power_driver._power_control_seamicro15k_ipmi(
            ip, username, password, server_id, power_change
        )
        power_mode = 1 if power_change == "on" else 6

        call_and_check_mock.assert_called_once_with(
            [
                "ipmitool",
                "-I",
                "lanplus",
                "-H",
                ip,
                "-U",
                username,
                "-P",
                password,
                "-L",
                "OPERATOR",
                "raw",
                "0x2E",
                "1",
                "0x00",
                "0x7d",
                "0xab",
                power_mode,
                "0",
                server_id,
            ]
        )

    def test_power_control_seamicro15k_ipmi_raises_PowerFatalError(self):
        ip, username, password, server_id, _ = self.make_context()
        power_change = choice(["on", "off"])
        seamicro_power_driver = SeaMicroPowerDriver()
        call_and_check_mock = self.patch(seamicro_module, "call_and_check")
        call_and_check_mock.side_effect = ExternalProcessError(
            1, "ipmitool something"
        )

        self.assertRaises(
            PowerActionError,
            seamicro_power_driver._power_control_seamicro15k_ipmi,
            ip,
            username,
            password,
            server_id,
            power_change,
        )

    def test_power_calls__power_control_seamicro15k_ipmi(self):
        ip, username, password, server_id, context = self.make_context()
        context["power_control"] = "ipmi"
        power_change = choice(["on", "off"])
        seamicro_power_driver = SeaMicroPowerDriver()
        _power_control_seamicro15k_ipmi_mock = self.patch(
            seamicro_power_driver, "_power_control_seamicro15k_ipmi"
        )
        seamicro_power_driver._power(power_change, context)

        _power_control_seamicro15k_ipmi_mock.assert_called_once_with(
            ip, username, password, server_id, power_change=power_change
        )

    def test_power_calls_power_control_seamicro15k_v09(self):
        ip, username, password, server_id, context = self.make_context()
        context["power_control"] = "restapi"
        power_change = choice(["on", "off"])
        seamicro_power_driver = SeaMicroPowerDriver()
        power_control_seamicro15k_v09_mock = self.patch(
            seamicro_module, "power_control_seamicro15k_v09"
        )
        seamicro_power_driver._power(power_change, context)

        power_control_seamicro15k_v09_mock.assert_called_once_with(
            ip, username, password, server_id, power_change=power_change
        )

    def test_power_calls_power_control_seamicro15k_v2(self):
        ip, username, password, server_id, context = self.make_context()
        context["power_control"] = "restapi2"
        power_change = choice(["on", "off"])
        seamicro_power_driver = SeaMicroPowerDriver()
        power_control_seamicro15k_v2_mock = self.patch(
            seamicro_module, "power_control_seamicro15k_v2"
        )
        seamicro_power_driver._power(power_change, context)

        power_control_seamicro15k_v2_mock.assert_called_once_with(
            ip, username, password, server_id, power_change=power_change
        )

    def test_power_on_calls_power(self):
        _, _, _, _, context = self.make_context()
        context["power_control"] = factory.make_name("power_control")
        seamicro_power_driver = SeaMicroPowerDriver()
        power_mock = self.patch(seamicro_power_driver, "_power")
        seamicro_power_driver.power_on(context["system_id"], context)

        power_mock.assert_called_once_with("on", context)

    def test_power_off_calls_power(self):
        _, _, _, _, context = self.make_context()
        context["power_control"] = factory.make_name("power_control")
        seamicro_power_driver = SeaMicroPowerDriver()
        power_mock = self.patch(seamicro_power_driver, "_power")
        seamicro_power_driver.power_off(context["system_id"], context)

        power_mock.assert_called_once_with("off", context)

    def test_power_query_calls_power_query_seamicro15k_v2(self):
        ip, username, password, server_id, context = self.make_context()
        context["power_control"] = "restapi2"
        seamicro_power_driver = SeaMicroPowerDriver()
        power_query_seamicro15k_v2_mock = self.patch(
            seamicro_module, "power_query_seamicro15k_v2"
        )
        power_query_seamicro15k_v2_mock.return_value = "on"
        power_state = seamicro_power_driver.power_query(
            context["system_id"], context
        )

        power_query_seamicro15k_v2_mock.assert_called_once_with(
            ip,
            username,
            password,
            server_id,
        )
        self.assertEqual(power_state, "on")

    def test_power_query_returns_unknown_if_not_restapi2(self):
        ip, username, password, server_id, context = self.make_context()
        context["power_control"] = factory.make_name("power_control")
        seamicro_power_driver = SeaMicroPowerDriver()
        power_state = seamicro_power_driver.power_query(
            context["system_id"], context
        )

        self.assertEqual("unknown", power_state)
