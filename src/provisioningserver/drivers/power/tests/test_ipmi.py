# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ipmi`."""

import random
from unittest.mock import ANY, call, sentinel

from maascommon.enums.ipmi import IPMIPrivilegeLevel
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import ipmi as ipmi_module
from provisioningserver.drivers.power import (
    PowerAuthError,
    PowerError,
    PowerSettingError,
)
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


def _make_ipmi_base_command(
    binary,
    *,
    power_driver=None,
    power_address=None,
    power_user=None,
    power_pass=None,
    k_g=None,
    cipher_suite_id=None,
    privilege_level=None,
    **_extra,
):
    """Return the shared IPMI command prefix for ipmipower/ipmi-chassis-config."""
    ret = (
        binary,
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


def make_ipmi_chassis_config_command(
    ipmi_chassis_config=None,
    tmp_config_name=None,
    **kwargs,
):
    """Make and return a command for ipmi-chassis-config subprocess."""
    ret = _make_ipmi_base_command(ipmi_chassis_config, **kwargs)
    ret += ("--commit", "--filename", tmp_config_name)
    return ret


def make_ipmipower_command(
    ipmipower=None,
    **kwargs,
):
    """Make and return a command for ipmipower subprocess."""
    return _make_ipmi_base_command(ipmipower, **kwargs)


class TestIPMIPowerDriver(MAASTestCase):
    def _assert_chassis_config_written(
        self, *, power_boot_type=None, expected_config=IPMI_CONFIG
    ):
        if power_boot_type is not None:
            boot_type = self.patch(ipmi_module, "power_boot_type")
            boot_type.return_value = power_boot_type
        NamedTemporaryFile = self.patch(ipmi_module, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")

        kwargs = (
            {"power_boot_type": power_boot_type}
            if power_boot_type is not None
            else {}
        )
        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            ["true"], sentinel.change, sentinel.addr, **kwargs
        )

        NamedTemporaryFile.assert_called_once_with("w+", encoding="utf-8")
        tmpfile.__enter__.assert_called_once_with()
        tmpfile.write.assert_called_once_with(expected_config)
        tmpfile.flush.assert_called_once_with()
        tmpfile.__exit__.assert_called_once_with(None, None, None)

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
        self._assert_chassis_config_written()

    def test_chassis_config_written_to_temporary_file_with_boot_type(self):
        self._assert_chassis_config_written(
            power_boot_type=IPMI_BOOT_TYPE.EFI,
            expected_config=IPMI_CONFIG_WITH_BOOT_TYPE
            % IPMI_BOOT_TYPE_MAPPING[IPMI_BOOT_TYPE.EFI],
        )

    def _assert_power_command(self, **context_overrides):
        """Verify _issue_ipmi_command builds the expected ipmipower command."""
        context = make_context()
        context.update(context_overrides)
        context["mac_address"] = factory.make_mac_address()
        context["k_g"] = None
        context["cipher_suite_id"] = "17"

        driver = IPMIPowerDriver()
        power_change = random.choice(("on", "off"))
        self.patch_autospec(driver, "_issue_ipmipower_command")
        driver._issue_ipmi_command(power_change, **context)

        workaround_flags = context.get("workaround_flags") or []
        expected_cmd = [
            "ipmipower",
            "-W",
            ",".join(workaround_flags) if workaround_flags else "opensesspriv",
            "--driver-type",
            context["power_driver"],
            "-h",
            context["power_address"],
            "-u",
            context["power_user"],
            "-p",
            context["power_pass"],
            "-I",
            context["cipher_suite_id"],
            "-l",
            context.get("privilege_level", "OPERATOR"),
        ]
        if power_change == "on":
            expected_cmd.extend(["--cycle", "--on-if-off"])
        else:
            expected_cmd.extend(["--off"])

        self.assertEqual(
            driver._issue_ipmipower_command.call_args[0][0], expected_cmd
        )

    def test_power_command_uses_default_workaround(self):
        self._assert_power_command()

    def test_power_command_uses_overriden_workaround(self):
        self._assert_power_command(
            workaround_flags=[
                random.choice(
                    [choice[0] for choice in IPMI_WORKAROUND_FLAG_CHOICES]
                )
            ]
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

    def test_power_calls__issue_ipmi_command(self):
        for op in ("on", "off", "query"):
            context = make_context()
            ipmi_power_driver = IPMIPowerDriver()
            mock = self.patch(ipmi_power_driver, "_issue_ipmi_command")
            system_id = factory.make_name("system_id")
            getattr(ipmi_power_driver, f"power_{op}")(system_id, context)

            mock.assert_called_once_with(op, **context)

    def test_power_retires_on_kg_error(self):
        for op in ("on", "off", "query"):
            context = make_context()
            k_g = context.pop("k_g", factory.make_name("k_g"))
            ipmi_power_driver = IPMIPowerDriver()
            mock = self.patch(ipmi_power_driver, "_issue_ipmi_command")
            k_g_error = IPMI_ERRORS["k_g invalid"]
            mock.side_effect = (
                k_g_error["exception"](k_g_error["message"]),
                None,
            )
            system_id = factory.make_name("system_id")

            getattr(ipmi_power_driver, f"power_{op}")(
                system_id, {"k_g": k_g, **context}
            )

            mock.assert_has_calls(
                [
                    call(op, **{"k_g": k_g, **context}),
                    call(op, **context),
                ]
            )

    def test_power_raises_error_after_retires_on_kg_error(self):
        for op in ("on", "off", "query"):
            context = make_context()
            k_g = context.pop("k_g", factory.make_name("k_g"))
            ipmi_power_driver = IPMIPowerDriver()
            mock = self.patch(ipmi_power_driver, "_issue_ipmi_command")
            k_g_error = IPMI_ERRORS["k_g invalid"]
            mock.side_effect = k_g_error["exception"](k_g_error["message"])
            system_id = factory.make_name("system_id")

            self.assertRaises(
                k_g_error["exception"],
                getattr(ipmi_power_driver, f"power_{op}"),
                system_id,
                {"k_g": k_g, **context},
            )
            mock.assert_has_calls(
                [
                    call(op, **{"k_g": k_g, **context}),
                    call(op, **context),
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


class TestIPMIPowerDriverFIPS(MAASTestCase):
    """FIPS allow-list semantics for IPMI cipher suite selection."""

    def _make_context(self):
        context = make_context()
        context["mac_address"] = factory.make_mac_address()
        context["k_g"] = None
        return context

    def test_fips_rejects_cipher_suites(self):
        """In FIPS mode, cipher suites 3, 8, 12 are not on the allow-list."""
        for cipher_suite_id in ("3", "8", "12"):
            with self.subTest(cipher_suite_id=cipher_suite_id):
                self.patch(ipmi_module, "is_fips_enabled", lambda: True)
                driver = IPMIPowerDriver()
                context = self._make_context()
                context["cipher_suite_id"] = cipher_suite_id
                self.assertRaises(
                    PowerSettingError,
                    driver._issue_ipmi_command,
                    "on",
                    **context,
                )

    def test_fips_defaults_cipher_suite_to_17(self):
        """In FIPS mode, empty/unset/explicit-17 all yield '-I 17' in the command."""
        scenarios = (("", "empty"), (None, "unset"), ("17", "explicit"))
        for cipher_suite_id, scenario in scenarios:
            with self.subTest(scenario=scenario):
                self.patch(ipmi_module, "is_fips_enabled", lambda: True)
                driver = IPMIPowerDriver()
                context = self._make_context()
                if cipher_suite_id is None:
                    context.pop("cipher_suite_id", None)
                else:
                    context["cipher_suite_id"] = cipher_suite_id
                self.patch_autospec(driver, "_issue_ipmipower_command")
                # Must not raise in any of these scenarios.
                driver._issue_ipmi_command("on", **context)
                cmd = driver._issue_ipmipower_command.call_args[0][0]
                self.assertIn("-I", cmd)
                idx = cmd.index("-I")
                self.assertEqual(cmd[idx + 1], "17")
