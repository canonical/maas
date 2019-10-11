# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ipmi`."""

__all__ = []

import random
from subprocess import PIPE
from unittest.mock import ANY, call, sentinel

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import (
    ipmi as ipmi_module,
    PowerAuthError,
    PowerError,
)
from provisioningserver.drivers.power.ipmi import (
    IPMI_BOOT_TYPE,
    IPMI_BOOT_TYPE_MAPPING,
    IPMI_CONFIG,
    IPMI_CONFIG_WITH_BOOT_TYPE,
    IPMI_ERRORS,
    IPMIPowerDriver,
)
from provisioningserver.utils.shell import (
    get_env_with_locale,
    has_command_available,
)
from testtools.matchers import Contains, Equals


def make_context():
    """Make and return a context for IPMI Power Driver."""
    return {
        "power_address": factory.make_name("power_address"),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
        "power_driver": factory.make_name("power_driver"),
        "power_off_mode": factory.make_name("power_off_mode"),
        "ipmipower": "ipmipower",
        "ipmi_chassis_config": "ipmi-chassis-config",
    }


def make_ipmi_chassis_config_command(
    ipmi_chassis_config=None,
    power_address=None,
    power_pass=None,
    power_driver=None,
    power_user=None,
    tmp_config_name=None,
    **extra
):
    """Make and return a command for ipmi-chassis-config subprocess."""
    return (
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
        "--commit",
        "--filename",
        tmp_config_name,
    )


def make_ipmipower_command(
    ipmipower=None,
    power_address=None,
    power_pass=None,
    power_driver=None,
    power_user=None,
    **extra
):
    """Make and return a command for ipmipower subprocess."""
    return (
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


class TestIPMIPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = ipmi_module.IPMIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["freeipmi-tools"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = ipmi_module.IPMIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def test__finds_power_address_from_mac_address(self):
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
        self.assertThat(
            driver._issue_ipmipower_command,
            MockCalledOnceWith(ANY, power_change, ip_address),
        )
        # The IP address is also within the command passed to
        # _issue_ipmipower_command.
        self.assertThat(
            driver._issue_ipmipower_command.call_args[0], Contains(ip_address)
        )

    def test__chassis_config_written_to_temporary_file(self):
        NamedTemporaryFile = self.patch(ipmi_module, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")

        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            ["true"], sentinel.change, sentinel.addr
        )

        self.assertThat(
            NamedTemporaryFile, MockCalledOnceWith("w+", encoding="utf-8")
        )
        self.assertThat(tmpfile.__enter__, MockCalledOnceWith())
        self.assertThat(tmpfile.write, MockCalledOnceWith(IPMI_CONFIG))
        self.assertThat(tmpfile.flush, MockCalledOnceWith())
        self.assertThat(tmpfile.__exit__, MockCalledOnceWith(None, None, None))

    def test__issue_ipmi_chassis_config_command_raises_power_auth_error(self):
        ipmi_errors = {
            key: IPMI_ERRORS[key]
            for key in IPMI_ERRORS
            if IPMI_ERRORS[key]["exception"] == PowerAuthError
        }
        for error, error_info in ipmi_errors.items():
            popen_mock = self.patch(ipmi_module, "Popen")
            process = popen_mock.return_value
            process.communicate.return_value = (b"", error.encode("utf-8"))
            self.assertRaises(
                error_info.get("exception"),
                IPMIPowerDriver._issue_ipmi_chassis_config_command,
                factory.make_name("command"),
                factory.make_name("power_change"),
                factory.make_name("power_address"),
            )

    def test__issue_ipmi_chassis_config_command_logs_maaslog_warning(self):
        power_address = factory.make_name("power_address")
        stderr = factory.make_name("stderr")
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        process.communicate.return_value = (b"", stderr.encode("utf-8"))
        maaslog = self.patch(ipmi_module, "maaslog")
        IPMIPowerDriver._issue_ipmi_chassis_config_command(
            factory.make_name("command"),
            factory.make_name("power_change"),
            power_address,
        )
        self.assertThat(
            maaslog.warning,
            MockCalledOnceWith(
                "Failed to change the boot order to PXE %s: %s"
                % (power_address, stderr)
            ),
        )

    def test__issue_ipmipower_command_raises_error(self):
        for error, error_info in IPMI_ERRORS.items():
            popen_mock = self.patch(ipmi_module, "Popen")
            process = popen_mock.return_value
            process.communicate.return_value = (error.encode("utf-8"), b"")
            self.assertRaises(
                error_info.get("exception"),
                IPMIPowerDriver._issue_ipmipower_command,
                factory.make_name("command"),
                factory.make_name("power_change"),
                factory.make_name("power_address"),
            )

    def test__issue_ipmipower_command_raises_unknown_error(self):
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        process.communicate.return_value = (b"", b"error")
        self.assertRaises(
            PowerError,
            IPMIPowerDriver._issue_ipmipower_command,
            factory.make_name("command"),
            factory.make_name("power_change"),
            factory.make_name("power_address"),
        )

    def test__issue_ipmipower_command_does_not_mistake_host_for_status(self):
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        # "cameron" contains the string "on", but the machine is off.
        process.communicate.return_value = (b"cameron: off", b"")
        process.returncode = 0
        self.assertThat(
            IPMIPowerDriver._issue_ipmipower_command(
                factory.make_name("command"),
                "query",
                factory.make_name("address"),
            ),
            Equals("off"),
        )

    def test__issue_ipmi_command_issues_power_on(self):
        context = make_context()
        ipmi_chassis_config_command = make_ipmi_chassis_config_command(
            **context, tmp_config_name=ANY
        )
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--cycle", "--on-if-off")
        ipmi_power_driver = IPMIPowerDriver()
        env = get_env_with_locale()
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        process.communicate.side_effect = [(b"", b""), (b"on", b"")]
        process.returncode = 0

        result = ipmi_power_driver._issue_ipmi_command("on", **context)

        self.expectThat(
            popen_mock,
            MockCallsMatch(
                call(
                    ipmi_chassis_config_command,
                    stdout=PIPE,
                    stderr=PIPE,
                    env=env,
                ),
                call(ipmipower_command, stdout=PIPE, stderr=PIPE, env=env),
            ),
        )
        self.expectThat(result, Equals("on"))

    def test__issue_ipmi_command_issues_power_off(self):
        context = make_context()
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--off",)
        ipmi_power_driver = IPMIPowerDriver()
        env = get_env_with_locale()
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        process.communicate.side_effect = [(b"off", b"")]
        process.returncode = 0

        result = ipmi_power_driver._issue_ipmi_command("off", **context)

        self.expectThat(
            popen_mock,
            MockCallsMatch(
                call(ipmipower_command, stdout=PIPE, stderr=PIPE, env=env)
            ),
        )
        self.expectThat(result, Equals("off"))

    def test__issue_ipmi_command_issues_power_off_soft_mode(self):
        context = make_context()
        context["power_off_mode"] = "soft"
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--soft",)
        ipmi_power_driver = IPMIPowerDriver()
        env = get_env_with_locale()
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        process.communicate.side_effect = [(b"off", b"")]
        process.returncode = 0

        result = ipmi_power_driver._issue_ipmi_command("off", **context)

        self.expectThat(
            popen_mock,
            MockCallsMatch(
                call(ipmipower_command, stdout=PIPE, stderr=PIPE, env=env)
            ),
        )
        self.expectThat(result, Equals("off"))

    def test__issue_ipmi_command_issues_power_query(self):
        context = make_context()
        ipmipower_command = make_ipmipower_command(**context)
        ipmipower_command += ("--stat",)
        ipmi_power_driver = IPMIPowerDriver()
        env = get_env_with_locale()
        popen_mock = self.patch(ipmi_module, "Popen")
        process = popen_mock.return_value
        process.communicate.return_value = (b"other", b"")
        process.returncode = 0

        result = ipmi_power_driver._issue_ipmi_command("query", **context)

        self.expectThat(
            popen_mock,
            MockCalledOnceWith(
                ipmipower_command, stdout=PIPE, stderr=PIPE, env=env
            ),
        )
        self.expectThat(result, Equals("other"))

    def test_power_on_calls__issue_ipmi_command(self):
        context = make_context()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        system_id = factory.make_name("system_id")
        ipmi_power_driver.power_on(system_id, context)

        self.assertThat(
            _issue_ipmi_command_mock, MockCalledOnceWith("on", **context)
        )

    def test_power_off_calls__issue_ipmi_command(self):
        context = make_context()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        system_id = factory.make_name("system_id")
        ipmi_power_driver.power_off(system_id, context)

        self.assertThat(
            _issue_ipmi_command_mock, MockCalledOnceWith("off", **context)
        )

    def test_power_query_calls__issue_ipmi_command(self):
        context = make_context()
        ipmi_power_driver = IPMIPowerDriver()
        _issue_ipmi_command_mock = self.patch(
            ipmi_power_driver, "_issue_ipmi_command"
        )
        system_id = factory.make_name("system_id")
        ipmi_power_driver.power_query(system_id, context)

        self.assertThat(
            _issue_ipmi_command_mock, MockCalledOnceWith("query", **context)
        )

    def test__issue_ipmi_chassis_config_with_power_boot_type(self):
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
        self.assertThat(
            driver._issue_ipmi_chassis_config_command,
            MockCalledOnceWith(
                ANY,
                power_change,
                ip_address,
                power_boot_type=IPMI_BOOT_TYPE.EFI,
            ),
        )
        # The IP address is also within the command passed to
        # _issue_ipmi_chassis_config_command.
        self.assertThat(
            driver._issue_ipmi_chassis_config_command.call_args[0],
            Contains(ip_address),
        )
        # The IP address is passed to _issue_ipmipower_command.
        self.assertThat(
            driver._issue_ipmipower_command,
            MockCalledOnceWith(ANY, power_change, ip_address),
        )

    def test__chassis_config_written_to_temporary_file_with_boot_type(self):
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

        self.assertThat(
            NamedTemporaryFile, MockCalledOnceWith("w+", encoding="utf-8")
        )
        self.assertThat(tmpfile.__enter__, MockCalledOnceWith())
        self.assertThat(
            tmpfile.write,
            MockCalledOnceWith(
                IPMI_CONFIG_WITH_BOOT_TYPE
                % IPMI_BOOT_TYPE_MAPPING[IPMI_BOOT_TYPE.EFI]
            ),
        )
        self.assertThat(tmpfile.flush, MockCalledOnceWith())
        self.assertThat(tmpfile.__exit__, MockCalledOnceWith(None, None, None))
