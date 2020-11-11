# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.apc`."""


from testtools.matchers import Equals

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import apc as apc_module
from provisioningserver.drivers.power import PowerActionError
from provisioningserver.utils.shell import has_command_available, ProcessResult

COMMON_ARGS = "-c private -v1 {} .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.{}"
COMMON_OUTPUT = "iso.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%s = INTEGER: 1\n"


class TestAPCPowerDriver(MAASTestCase):
    def make_context(self):
        return {
            "power_address": factory.make_name("power_address"),
            "node_outlet": factory.make_name("node_outlet"),
            "power_on_delay": "5",
        }

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = apc_module.APCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["snmp"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = apc_module.APCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def patch_run_command(self, stdout="", stderr="", returncode=0):
        mock_run_command = self.patch(apc_module.shell, "run_command")
        mock_run_command.return_value = ProcessResult(
            stdout=stdout, stderr=stderr, returncode=returncode
        )
        return mock_run_command

    def test_run_process_calls_command_and_returns_output(self):
        driver = apc_module.APCPowerDriver()
        context = self.make_context()
        command = ["snmpget"] + COMMON_ARGS.format(
            context["power_address"], context["node_outlet"]
        ).split()
        mock_run_command = self.patch_run_command(
            stdout=COMMON_OUTPUT % context["node_outlet"],
            stderr="error_output",
        )
        output = driver.run_process(*command)
        mock_run_command.assert_called_once_with(*command)
        self.expectThat(output, Equals(apc_module.APCState.ON))

    def test_run_process_crashes_on_external_process_error(self):
        driver = apc_module.APCPowerDriver()
        self.patch_run_command(returncode=1)
        self.assertRaises(
            PowerActionError, driver.run_process, factory.make_name("command")
        )

    def test_run_process_crashes_on_no_power_state_match_found(self):
        driver = apc_module.APCPowerDriver()
        self.patch_run_command(stdout="Error")
        self.assertRaises(
            PowerActionError, driver.run_process, factory.make_name("command")
        )

    def test_power_on_calls_run_process(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "on"
        self.patch(driver, "power_off")
        mock_sleep = self.patch(apc_module, "sleep")
        mock_run_process = self.patch(driver, "run_process")
        driver.power_on(system_id, context)

        self.expectThat(
            mock_power_query, MockCalledOnceWith(system_id, context)
        )
        self.expectThat(
            mock_sleep, MockCalledOnceWith(float(context["power_on_delay"]))
        )
        command = (
            ["snmpset"]
            + COMMON_ARGS.format(
                context["power_address"], context["node_outlet"]
            ).split()
            + ["i", "1"]
        )
        mock_run_process.assert_called_once_with(*command)

    def test_power_off_calls_run_process(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        driver.power_off(system_id, context)
        command = (
            ["snmpset"]
            + COMMON_ARGS.format(
                context["power_address"], context["node_outlet"]
            ).split()
            + ["i", "2"]
        )
        mock_run_process.assert_called_once_with(*command)

    def test_power_query_returns_power_state_on(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = apc_module.APCState.ON
        result = driver.power_query(system_id, context)
        command = ["snmpget"] + COMMON_ARGS.format(
            context["power_address"], context["node_outlet"]
        ).split()
        mock_run_process.assert_called_once_with(*command)
        self.expectThat(result, Equals("on"))

    def test_power_query_returns_power_state_off(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = apc_module.APCState.OFF
        result = driver.power_query(system_id, context)
        command = ["snmpget"] + COMMON_ARGS.format(
            context["power_address"], context["node_outlet"]
        ).split()
        mock_run_process.assert_called_once_with(*command)
        self.expectThat(result, Equals("off"))

    def test_power_query_crashes_for_uknown_power_state(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = "Error"
        self.assertRaises(
            PowerActionError, driver.power_query, system_id, context
        )
