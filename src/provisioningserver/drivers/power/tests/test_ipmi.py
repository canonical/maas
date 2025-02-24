# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ipmi`."""

import random
from unittest.mock import ANY, call, sentinel

from maascommon.enums.ipmi import IPMIPrivilegeLevel
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import ipmi as ipmi_module
from provisioningserver.drivers.power import PowerAuthError, PowerError
from provisioningserver.drivers.power.ipmi import (
    IPMI_BOOT_TYPE,
    IPMI_BOOT_TYPE_MAPPING,
    IPMI_CIPHER_SUITE_ID_CHOICES,
    IPMI_CONFIG,
    IPMI_CONFIG_WITH_BOOT_TYPE,
    IPMI_ERRORS,
    IPMI_PRIVILEGE_LEVEL_CHOICES,
    IPMI_WORKAROUND_FLAG_CHOICES,
    IPMIPowerDriver,
)
from provisioningserver.utils.shell import has_command_available, ProcessResult


def make_context():
    """Make and return a context for IPMI Power Driver."""
    ret = {
        "power_address": factory.make_name("power_address"),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
        "power_driver": factory.make_name("power_driver"),
        "power_off_mode": factory.make_name("power_off_mode"),
        "ipmipower": "ipmipower",
        "ipmi_chassis_config": "ipmi-chassis-config",
    }
    # These options were added in MAAS 2.9. Add them optionally
    # to test users coming from older versions.
    if factory.pick_bool():
        ret["k_g"] = factory.make_name("k_g")
    if factory.pick_bool():
        ret["cipher_suite_id"] = random.choice(IPMI_CIPHER_SUITE_ID_CHOICES)[0]
    if factory.pick_bool():
        ret["privilege_level"] = random.choice(IPMI_PRIVILEGE_LEVEL_CHOICES)[0]
    return ret


def make_ipmi_chassis_config_command(
    ipmi_chassis_config=None,
    power_address=None,
    power_pass=None,
    power_driver=None,
    power_user=None,
    tmp_config_name=None,
    k_g=None,
    cipher_suite_id=None,
    privilege_level=None,
    **extra,
):
    """Make and return a command for ipmi-chassis-config subprocess."""
    ret = (
        ipmi_chassis_config,
        "-W",
        "opensesspriv",
        "--driver-type",
        power_driver,
        "-h",
        power_address,
        "-u",
        power_user,
        "-p",
        power_pass,
    )
    if k_g:
        ret += ("-k", k_g)
    if cipher_suite_id:
        ret += ("-I", cipher_suite_id)
    if privilege_level:
        ret += ("-l", privilege_level)
    else:
        ret += ("-l", IPMIPrivilegeLevel.OPERATOR.name)
    ret += (
        "--commit",
        "--filename",
        tmp_config_name,
    )
    return ret


def make_ipmipower_command(
    ipmipower=None,
    power_address=None,
    power_pass=None,
    power_driver=None,
    power_user=None,
    k_g=None,
    cipher_suite_id=None,
    privilege_level=None,
    **extra,
):
    """Make and return a command for ipmipower subprocess."""
    ret = (
        ipmipower,
        "-W",
        "opensesspriv",
        "--driver-type",
        power_driver,
        "-h",
        power_address,
        "-u",
        power_user,
        "-p",
        power_pass,
    )
    if k_g:
        ret += ("-k", k_g)
    if cipher_suite_id:
        ret += ("-I", cipher_suite_id)
    if privilege_level:
        ret += ("-l", privilege_level)
    else:
        ret += ("-l", IPMIPrivilegeLevel.OPERATOR.name)
    return ret


class TestIPMIPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = ipmi_module.IPMIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["freeipmi-tools"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = ipmi_module.IPMIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_finds_power_address_from_mac_address(self):
        context = make_context()
        driver = IPMIPowerDriver()
        ip_address = factory.make_ipv4_address()
        find_ip_via_arp = self.patch(ipmi_module, "find_ip_via_arp")
        find_ip_via_arp.return_value = ip_address
        power_change = random.choice(("on", "off"))

        context["mac_address"] = factory.make_mac_address()
        context["power_address"] = random.choice((None, "", "   "))

        self.patch_autospec(driver, "_issue_ipmipower_command")
        driver._issue_ipmi_command(power_change, **context)

        # The IP address is passed to _issue_ipmipower_command.
        driver._issue_ipmipower_command.assert_called_once_with(
            ANY, power_change, ip_address
        )
        # The IP address is also within the command passed to
        # _issue_ipmipower_command.
        self.assertIn(ip_address, driver._issue_ipmipower_command.call_args[0])

    def test_chassis_config_written_to_temporary_file(self):
        NamedTemporaryFile = self.patch(ipmi_module, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")

        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            ["true"], sentinel.change, sentinel.addr
        )

        NamedTemporaryFile.assert_called_once_with("w+", encoding="utf-8")
        tmpfile.__enter__.assert_called_once_with()
        tmpfile.write.assert_called_once_with(IPMI_CONFIG)
        tmpfile.flush.assert_called_once_with()
        tmpfile.__exit__.assert_called_once_with(None, None, None)

    def test_power_command_uses_default_workaround(self):
        context = make_context()
        driver = IPMIPowerDriver()
        power_change = random.choice(("on", "off"))

        context["mac_address"] = factory.make_mac_address()
        context["k_g"] = None
        context["cipher_suite_id"] = "17"

        self.patch_autospec(driver, "_issue_ipmipower_command")

        driver._issue_ipmi_command(power_change, **context)

        expected_cmd = [
            "ipmipower",
            "-W",
            "opensesspriv",
            "--driver-type",
            context.get("power_driver"),
            "-h",
            context.get("power_address"),
            "-u",
            context.get("power_user"),
            "-p",
            context.get("power_pass"),
            "-I",
            context.get("cipher_suite_id"),
            "-l",
            context.get("privilege_level", "OPERATOR"),
        ]
        if power_change == "on":
            expected_cmd.extend(["--cycle", "--on-if-off"])
        else:
            expected_cmd.extend(["--off"])

        self.assertCountEqual(
            driver._issue_ipmipower_command.call_args[0][0], expected_cmd
        )

    def test_power_command_uses_overriden_workaround(self):
        context = make_context()
        driver = IPMIPowerDriver()
        power_change = random.choice(("on", "off"))

        context["mac_address"] = factory.make_mac_address()
        context["k_g"] = None
        context["cipher_suite_id"] = "17"
        context["workaround_flags"] = [
            random.choice(
                [choice[0] for choice in IPMI_WORKAROUND_FLAG_CHOICES]
            )
        ]

        self.patch_autospec(driver, "_issue_ipmipower_command")

        driver._issue_ipmi_command(power_change, **context)

        expected_cmd = [
            "ipmipower",
            "-W",
            ",".join(flag for flag in context.get("workaround_flags", [])),
            "--driver-type",
            context.get("power_driver"),
            "-h",
            context.get("power_address"),
            "-u",
            context.get("power_user"),
            "-p",
            context.get("power_pass"),
            "-I",
            context.get("cipher_suite_id"),
            "-l",
            context.get("privilege_level", "OPERATOR"),
        ]
        if power_change == "on":
            expected_cmd.extend(["--cycle", "--on-if-off"])
        else:
            expected_cmd.extend(["--off"])

        self.assertCountEqual(
            driver._issue_ipmipower_command.call_args[0][0], expected_cmd
        )

    def test_issue_ipmi_chassis_config_command_raises_power_auth_error(self):
        ipmi_errors = {
            key: IPMI_ERRORS[key]
            for key in IPMI_ERRORS
            if IPMI_ERRORS[key]["exception"] == PowerAuthError
        }
        for error, error_info in ipmi_errors.items():
            run_command_mock = self.patch(ipmi_module.shell, "run_command")
            run_command_mock.return_value = ProcessResult(stderr=error)
            self.assertRaises(
                error_info.get("exception"),
                IPMIPowerDriver._issue_ipmi_chassis_config_command,
                factory.make_name("command"),
                factory.make_name("power_change"),
                factory.make_name("power_address"),
            )

    def test_issue_ipmi_chassis_config_command_logs_maaslog_warning(self):
        power_address = factory.make_name("power_address")
        stderr = factory.make_name("stderr")
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        run_command_mock.return_value = ProcessResult(
            stderr=stderr, returncode=1
        )
        maaslog = self.patch(ipmi_module, "maaslog")
        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            [factory.make_name("command")],
            factory.make_name("power_change"),
            power_address,
        )
        maaslog.warning.assert_called_once_with(
            f"Failed to change the boot order to PXE {power_address}: {stderr}"
        )

    def test_issue_ipmipower_command_raises_error(self):
        for error, error_info in IPMI_ERRORS.items():
            run_command_mock = self.patch(ipmi_module.shell, "run_command")
            run_command_mock.return_value = ProcessResult(
                stdout=error, returncode=1
            )
            self.assertRaises(
                error_info.get("exception"),
                IPMIPowerDriver._issue_ipmipower_command,
                factory.make_name("command"),
                factory.make_name("power_change"),
                factory.make_name("power_address"),
            )

    def test_issue_ipmipower_command_raises_unknown_error(self):
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        run_command_mock.return_value = ProcessResult(
            stderr="error", returncode=1
        )
        self.assertRaises(
            PowerError,
            IPMIPowerDriver._issue_ipmipower_command,
            factory.make_name("command"),
            factory.make_name("power_change"),
            factory.make_name("power_address"),
        )

    def test_issue_ipmipower_command_does_not_mistake_host_for_status(self):
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        # "cameron" contains the string "on", but the machine is off.
        run_command_mock.return_value = ProcessResult(stdout="cameron: off")
        self.assertEqual(
            IPMIPowerDriver._issue_ipmipower_command(
                factory.make_name("command"),
                "query",
                factory.make_name("address"),
            ),
            "off",
        )

    def test_issue_ipmi_command_issues_power_on(self):
        context = make_context()
        ipmi_chassis_config_command = make_ipmi_chassis_config_command(
            **context, tmp_config_name=ANY
        )
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--cycle", "--on-if-off")
        ipmi_power_driver = IPMIPowerDriver()
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        run_command_mock.side_effect = [
            ProcessResult(),
            ProcessResult(stdout="on"),
        ]
        result = ipmi_power_driver._issue_ipmi_command("on", **context)
        run_command_mock.assert_has_calls(
            [call(*ipmi_chassis_config_command), call(*ipmipower_command)]
        )
        self.assertEqual(result, "on")

    def test_issue_ipmi_command_issues_power_off(self):
        context = make_context()
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--off",)
        ipmi_power_driver = IPMIPowerDriver()
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        run_command_mock.return_value = ProcessResult(stdout="off")
        result = ipmi_power_driver._issue_ipmi_command("off", **context)
        run_command_mock.assert_called_once_with(*ipmipower_command)
        self.assertEqual(result, "off")

    def test_issue_ipmi_command_issues_power_off_soft_mode(self):
        context = make_context()
        context["power_off_mode"] = "soft"
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--soft",)
        ipmi_power_driver = IPMIPowerDriver()
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        run_command_mock.return_value = ProcessResult(stdout="off")
        result = ipmi_power_driver._issue_ipmi_command("off", **context)
        run_command_mock.assert_called_once_with(*ipmipower_command)
        self.assertEqual(result, "off")

    def test_issue_ipmi_command_issues_power_query(self):
        context = make_context()
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--stat",)
        ipmi_power_driver = IPMIPowerDriver()
        run_command_mock = self.patch(ipmi_module.shell, "run_command")
        run_command_mock.return_value = ProcessResult(stdout="other")
        result = ipmi_power_driver._issue_ipmi_command("query", **context)
        run_command_mock.assert_called_once_with(*ipmipower_command)
        self.assertEqual(result, "other")

    def test_power_on_calls__issue_ipmi_command(self):
        context = make_context()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        system_id = factory.make_name("system_id")
        ipmi_power_driver.power_on(system_id, context)

        _issue_ipmi_command_mock.assert_called_once_with("on", **context)

    def test_power_on_retires_on_kg_error(self):
        context = make_context()
        k_g = context.pop("k_g", factory.make_name("k_g"))
        ipmi_power_driver = IPMIPowerDriver()
        mock_issue_ipmi_command = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        k_g_error = IPMI_ERRORS["k_g invalid"]
        mock_issue_ipmi_command.side_effect = (
            k_g_error["exception"](k_g_error["message"]),
            None,
        )
        system_id = factory.make_name("system_id")

        ipmi_power_driver.power_on(system_id, {"k_g": k_g, **context})

        mock_issue_ipmi_command.assert_has_calls(
            [
                call("on", **{"k_g": k_g, **context}),
                call("on", **context),
            ]
        )

    def test_power_on_raises_error_after_retires_on_kg_error(self):
        context = make_context()
        k_g = context.pop("k_g", factory.make_name("k_g"))
        ipmi_power_driver = IPMIPowerDriver()
        mock_issue_ipmi_command = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        k_g_error = IPMI_ERRORS["k_g invalid"]
        mock_issue_ipmi_command.side_effect = k_g_error["exception"](
            k_g_error["message"]
        )
        system_id = factory.make_name("system_id")

        self.assertRaises(
            k_g_error["exception"],
            ipmi_power_driver.power_on,
            system_id,
            {"k_g": k_g, **context},
        )
        mock_issue_ipmi_command.assert_has_calls(
            [
                call("on", **{"k_g": k_g, **context}),
                call("on", **context),
            ]
        )

    def test_power_off_calls__issue_ipmi_command(self):
        context = make_context()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        system_id = factory.make_name("system_id")
        ipmi_power_driver.power_off(system_id, context)

        _issue_ipmi_command_mock.assert_called_once_with("off", **context)

    def test_power_off_retires_on_kg_error(self):
        context = make_context()
        k_g = context.pop("k_g", factory.make_name("k_g"))
        ipmi_power_driver = IPMIPowerDriver()
        mock_issue_ipmi_command = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        k_g_error = IPMI_ERRORS["k_g invalid"]
        mock_issue_ipmi_command.side_effect = (
            k_g_error["exception"](k_g_error["message"]),
            None,
        )
        system_id = factory.make_name("system_id")

        ipmi_power_driver.power_off(system_id, {"k_g": k_g, **context})

        mock_issue_ipmi_command.assert_has_calls(
            [call("off", **{"k_g": k_g, **context}), call("off", **context)]
        )

    def test_power_off_raises_error_after_retires_on_kg_error(self):
        context = make_context()
        k_g = context.pop("k_g", factory.make_name("k_g"))
        ipmi_power_driver = IPMIPowerDriver()
        mock_issue_ipmi_command = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        k_g_error = IPMI_ERRORS["k_g invalid"]
        mock_issue_ipmi_command.side_effect = k_g_error["exception"](
            k_g_error["message"]
        )
        system_id = factory.make_name("system_id")

        self.assertRaises(
            k_g_error["exception"],
            ipmi_power_driver.power_off,
            system_id,
            {"k_g": k_g, **context},
        )
        mock_issue_ipmi_command.assert_has_calls(
            [
                call("off", **{"k_g": k_g, **context}),
                call("off", **context),
            ]
        )

    def test_power_query_calls__issue_ipmi_command(self):
        context = make_context()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        system_id = factory.make_name("system_id")
        ipmi_power_driver.power_query(system_id, context)

        _issue_ipmi_command_mock.assert_called_once_with("query", **context)

    def test_power_query_retires_on_kg_error(self):
        context = make_context()
        k_g = context.pop("k_g", factory.make_name("k_g"))
        ipmi_power_driver = IPMIPowerDriver()
        mock_issue_ipmi_command = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        k_g_error = IPMI_ERRORS["k_g invalid"]
        mock_issue_ipmi_command.side_effect = (
            k_g_error["exception"](k_g_error["message"]),
            None,
        )
        system_id = factory.make_name("system_id")

        ipmi_power_driver.power_query(system_id, {"k_g": k_g, **context})

        mock_issue_ipmi_command.assert_has_calls(
            [
                call("query", **{"k_g": k_g, **context}),
                call("query", **context),
            ]
        )

    def test_power_query_raises_error_after_retires_on_kg_error(self):
        context = make_context()
        k_g = context.pop("k_g", factory.make_name("k_g"))
        ipmi_power_driver = IPMIPowerDriver()
        mock_issue_ipmi_command = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        k_g_error = IPMI_ERRORS["k_g invalid"]
        mock_issue_ipmi_command.side_effect = k_g_error["exception"](
            k_g_error["message"]
        )
        system_id = factory.make_name("system_id")

        self.assertRaises(
            k_g_error["exception"],
            ipmi_power_driver.power_query,
            system_id,
            {"k_g": k_g, **context},
        )
        mock_issue_ipmi_command.assert_has_calls(
            [
                call("query", **{"k_g": k_g, **context}),
                call("query", **context),
            ]
        )

    def test_issue_ipmi_chassis_config_with_power_boot_type(self):
        context = make_context()
        driver = IPMIPowerDriver()
        ip_address = factory.make_ipv4_address()
        find_ip_via_arp = self.patch(ipmi_module, "find_ip_via_arp")
        find_ip_via_arp.return_value = ip_address
        power_change = "on"

        context["mac_address"] = factory.make_mac_address()
        context["power_address"] = random.choice((None, "", "   "))
        context["power_boot_type"] = IPMI_BOOT_TYPE.EFI

        self.patch_autospec(driver, "_issue_ipmi_chassis_config_command")
        self.patch_autospec(driver, "_issue_ipmipower_command")
        driver._issue_ipmi_command(power_change, **context)

        # The IP address is passed to _issue_ipmi_chassis_config_command.
        driver._issue_ipmi_chassis_config_command.assert_called_once_with(
            ANY,
            power_change,
            ip_address,
            power_boot_type=IPMI_BOOT_TYPE.EFI,
        )
        # The IP address is also within the command passed to
        # _issue_ipmi_chassis_config_command.
        self.assertIn(
            ip_address,
            driver._issue_ipmi_chassis_config_command.call_args[0],
        )
        # The IP address is passed to _issue_ipmipower_command.
        driver._issue_ipmipower_command.assert_called_once_with(
            ANY, power_change, ip_address
        )

    def test_chassis_config_written_to_temporary_file_with_boot_type(self):
        boot_type = self.patch(ipmi_module, "power_boot_type")
        boot_type.return_value = IPMI_BOOT_TYPE.EFI
        NamedTemporaryFile = self.patch(ipmi_module, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")

        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            ["true"],
            sentinel.change,
            sentinel.addr,
            power_boot_type=IPMI_BOOT_TYPE.EFI,
        )

        NamedTemporaryFile.assert_called_once_with("w+", encoding="utf-8")
        tmpfile.__enter__.assert_called_once_with()
        tmpfile.write.assert_called_once_with(
            IPMI_CONFIG_WITH_BOOT_TYPE
            % IPMI_BOOT_TYPE_MAPPING[IPMI_BOOT_TYPE.EFI]
        )
        tmpfile.flush.assert_called_once_with()
        tmpfile.__exit__.assert_called_once_with(None, None, None)
