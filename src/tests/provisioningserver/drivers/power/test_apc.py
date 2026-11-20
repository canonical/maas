# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.apc`."""

import random

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import apc as apc_module
from provisioningserver.drivers.power import PowerActionError
from provisioningserver.utils.shell import has_command_available, ProcessResult

COMMON_ARGS = "-c private -v1 {} .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.{}"
COMMON_OUTPUT = "iso.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%s = INTEGER: 1\n"


class TestAPCPowerDriver(MAASTestCase):
    def make_context(self, pdu_type=None, outlet=None):
        context = {
            "power_address": factory.make_name("power_address"),
            "node_outlet": (
                outlet if outlet is not None else random.randrange(1, 8)
            ),
            "power_on_delay": "5",
        }
        # Don't put pdu_type in the context by default, since driver
        # instance that were created before that setting was added won't
        # have it.
        if pdu_type is not None:
            context["pdu_type"] = pdu_type
        return context

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = apc_module.APCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["snmp"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = apc_module.APCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def patch_run_command(self, stdout="", stderr="", returncode=0):
        mock_run_command = self.patch(apc_module.shell, "run_command")
        mock_run_command.return_value = ProcessResult(
            stdout=stdout, stderr=stderr, returncode=returncode
        )
        return mock_run_command

    def test_run_process_calls_command_and_returns_output(self):
        driver = apc_module.APCPowerDriver()
        pdu_type = random.choice([None, "RPDU"])
        context = self.make_context(pdu_type=pdu_type)
        command = ["snmpget"] + COMMON_ARGS.format(
            context["power_address"], context["node_outlet"]
        ).split()
        mock_run_command = self.patch_run_command(
            stdout=COMMON_OUTPUT % context["node_outlet"],
            stderr="error_output",
        )
        output = driver.run_process(*command)
        mock_run_command.assert_called_once_with(*command)
        self.assertEqual(output, apc_module.APCState.ON)

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
        pdu_type = random.choice([None, "RPDU"])
        context = self.make_context(pdu_type=pdu_type)
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "on"
        self.patch(driver, "power_off")
        mock_sleep = self.patch(apc_module, "sleep")
        mock_run_process = self.patch(driver, "run_process")
        driver.power_on(system_id, context)

        mock_power_query.assert_called_once_with(system_id, context)
        mock_sleep.assert_called_once_with(float(context["power_on_delay"]))
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
        pdu_type = random.choice([None, "RPDU"])
        context = self.make_context(pdu_type=pdu_type)
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
        pdu_type = random.choice([None, "RPDU"])
        context = self.make_context(pdu_type=pdu_type)
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = apc_module.APCState.ON
        result = driver.power_query(system_id, context)
        command = ["snmpget"] + COMMON_ARGS.format(
            context["power_address"], context["node_outlet"]
        ).split()
        mock_run_process.assert_called_once_with(*command)
        self.assertEqual(result, "on")

    def test_power_query_returns_power_state_off(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        pdu_type = random.choice([None, "RPDU"])
        context = self.make_context(pdu_type=pdu_type)
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = apc_module.APCState.OFF
        result = driver.power_query(system_id, context)
        command = ["snmpget"] + COMMON_ARGS.format(
            context["power_address"], context["node_outlet"]
        ).split()
        mock_run_process.assert_called_once_with(*command)
        self.assertEqual(result, "off")

    def test_power_query_crashes_for_uknown_power_state(self):
        driver = apc_module.APCPowerDriver()
        system_id = factory.make_name("system_id")
        pdu_type = random.choice([None, "RPDU"])
        context = self.make_context(pdu_type=pdu_type)
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = "Error"
        self.assertRaises(
            PowerActionError, driver.power_query, system_id, context
        )

    def test_masterswitch(self):
        context = self.make_context(pdu_type="MASTERSWITCH", outlet=5)
        self.assertEqual(
            [
                "-c",
                "private",
                "-v1",
                context["power_address"],
                ".1.3.6.1.4.1.318.1.1.4.4.2.1.3.5",
            ],
            apc_module._get_common_args(context),
        )
