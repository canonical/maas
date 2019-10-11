# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.fence_cdu`."""

__all__ = []


from unittest.mock import call, sentinel

from hypothesis import given
from hypothesis.strategies import sampled_from
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import (
    fence_cdu as fence_cdu_module,
    PowerError,
)
from provisioningserver.utils.shell import (
    ExternalProcessError,
    get_env_with_locale,
    has_command_available,
)
from testtools.matchers import Equals


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

    def test__issue_fence_cdu_command(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        mock = self.patch(fence_cdu_module, "call_and_check")
        mock.return_value = b"test"
        stdout = driver._issue_fence_cdu_command(
            sentinel.command,
            sentinel.power_address,
            sentinel.power_id,
            sentinel.power_user,
            sentinel.power_pass,
        )
        self.expectThat(
            mock,
            MockCalledOnceWith(
                [
                    "fence_cdu",
                    "-a",
                    sentinel.power_address,
                    "-n",
                    sentinel.power_id,
                    "-l",
                    sentinel.power_user,
                    "-p",
                    sentinel.power_pass,
                    "-o",
                    sentinel.command,
                ],
                env=get_env_with_locale(),
            ),
        )
        self.expectThat(stdout, Equals("test"))

    def test__issue_fence_cdu_command_handles_power_query_off(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        mock = self.patch(fence_cdu_module, "call_and_check")
        mock.side_effect = ExternalProcessError(2, "Fence CDU error")
        stdout = driver._issue_fence_cdu_command(
            "status",
            sentinel.power_address,
            sentinel.power_id,
            sentinel.power_user,
            sentinel.power_pass,
        )
        self.assertThat(stdout, Equals("Status: OFF\n"))

    def test__issue_fence_cdu_command_errors_on_exception(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        mock = self.patch(fence_cdu_module, "call_and_check")
        mock.side_effect = ExternalProcessError(1, "Fence CDU error")
        self.assertRaises(
            PowerError,
            driver._issue_fence_cdu_command,
            sentinel.command,
            sentinel.power_address,
            sentinel.power_id,
            sentinel.power_user,
            sentinel.power_pass,
        )

    def make_context(self):
        return {
            "fence_cdu": "fence_cdu",
            "power_address": sentinel.power_address,
            "power_id": sentinel.power_id,
            "power_user": sentinel.power_user,
            "power_pass": sentinel.power_pass,
        }

    def test_power_on(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        environ = get_env_with_locale()
        context = self.make_context()
        mock = self.patch(fence_cdu_module, "call_and_check")
        mock.side_effect = (
            b"Status: ON\n",
            b"Status: OFF\n",
            b"Status: OFF\n",
            b"Status: ON\n",
        )
        self.patch(driver, "sleep")
        driver.power_on("fake_id", context)

        self.assertThat(
            mock,
            MockCallsMatch(
                call(
                    [
                        "fence_cdu",
                        "-a",
                        sentinel.power_address,
                        "-n",
                        sentinel.power_id,
                        "-l",
                        sentinel.power_user,
                        "-p",
                        sentinel.power_pass,
                        "-o",
                        "status",
                    ],
                    env=environ,
                ),
                call(
                    [
                        "fence_cdu",
                        "-a",
                        sentinel.power_address,
                        "-n",
                        sentinel.power_id,
                        "-l",
                        sentinel.power_user,
                        "-p",
                        sentinel.power_pass,
                        "-o",
                        "off",
                    ],
                    env=environ,
                ),
                call(
                    [
                        "fence_cdu",
                        "-a",
                        sentinel.power_address,
                        "-n",
                        sentinel.power_id,
                        "-l",
                        sentinel.power_user,
                        "-p",
                        sentinel.power_pass,
                        "-o",
                        "status",
                    ],
                    env=environ,
                ),
                call(
                    [
                        "fence_cdu",
                        "-a",
                        sentinel.power_address,
                        "-n",
                        sentinel.power_id,
                        "-l",
                        sentinel.power_user,
                        "-p",
                        sentinel.power_pass,
                        "-o",
                        "on",
                    ],
                    env=environ,
                ),
            ),
        )

    def test_power_on_crashes_when_power_cannot_be_cycled(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        context = self.make_context()
        mock = self.patch(fence_cdu_module, "call_and_check")
        mock.side_effect = (b"Status: ON\n", b"Status: OFF\n", b"Status: ON\n")
        self.patch(driver, "sleep")
        self.assertRaises(PowerError, driver.power_on, "fake_id", context)

    def test_power_off(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        context = self.make_context()
        mock = self.patch(driver, "_issue_fence_cdu_command")
        driver.power_off("fake_id", context)
        self.assertThat(mock, MockCalledOnceWith("off", **context))

    @given(sampled_from(["Status: ON\n", "Status: OFF\n"]))
    def test_power_query(self, cmd):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        context = self.make_context()
        mock = self.patch(driver, "_issue_fence_cdu_command")
        mock.return_value = cmd
        power_state = driver.power_query("fake_id", context)
        self.expectThat(mock, MockCalledOnceWith("status", **context))
        self.expectThat(power_state, Equals(cmd.split()[1].lower()))

    def test_power_query_errors_on_unknown_power_state(self):
        driver = fence_cdu_module.FenceCDUPowerDriver()
        context = self.make_context()
        mock = self.patch(driver, "_issue_fence_cdu_command")
        mock.return_value = "Garbage\n"
        self.assertRaises(PowerError, driver.power_query, "fake_id", context)
