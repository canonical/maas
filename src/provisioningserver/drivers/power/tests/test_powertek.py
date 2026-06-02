# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.powertek`."""

import random

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import PowerActionError
from provisioningserver.drivers.power import powertek as powertek_module
from provisioningserver.utils.shell import has_command_available, ProcessResult

COMMON_OUTPUT = "iso.3.6.1.4.1.42610.1.3.1.2.1.3.%s = INTEGER: 2\n"


class TestPowertekPowerDriver(MAASTestCase):
    def make_context(self, pdu_version=None, outlet=None, pdu_number=None):
        context = {
            "power_address": factory.make_name("power_address"),
            "node_outlet": (
                outlet if outlet is not None else random.randrange(1, 72)
            ),
            "pdu_number": pdu_number if pdu_number is not None else "1",
            "pdu_version": (
                pdu_version
                if pdu_version is not None
                else powertek_module.PowertekPDVersion.VERSION_1
            ),
            "power_community": "private",
        }
        return context

    def expected_v1_query_oid(self, context):
        return (
            ".%s.%s.2.1.5.%s"
            % (
                powertek_module.POWERTEK_PDU_VERSION_1_QUERY_OID,
                context["pdu_number"],
                context["node_outlet"],
            )
        )

    def expected_v1_control_oid(self, context):
        return (
            ".%s.%s.2.1.14.%s"
            % (
                powertek_module.POWERTEK_PDU_VERSION_1_CONTROL_OID,
                context["pdu_number"],
                context["node_outlet"],
            )
        )

    def expected_v2_oid(self, context):
        return (
            ".%s.%s.2.1.3.%s"
            % (
                powertek_module.POWERTEK_PDU_VERSION_2_OID,
                context["pdu_number"],
                context["node_outlet"],
            )
        )

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = powertek_module.PowertekPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["snmp"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = powertek_module.PowertekPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def patch_run_command(self, stdout="", stderr="", returncode=0):
        mock_run_command = self.patch(powertek_module.shell, "run_command")
        mock_run_command.return_value = ProcessResult(
            stdout=stdout, stderr=stderr, returncode=returncode
        )
        return mock_run_command

    def test_run_process_calls_command_and_returns_output(self):
        driver = powertek_module.PowertekPowerDriver()
        context = self.make_context(
            pdu_version=powertek_module.PowertekPDVersion.VERSION_2
        )
        command = [
            "snmpget",
            "-c",
            "private",
            "-v1",
            context["power_address"],
            self.expected_v2_oid(context),
        ]
        mock_run_command = self.patch_run_command(
            stdout=COMMON_OUTPUT % context["node_outlet"],
            stderr="error_output",
        )
        output = driver.run_process(*command)
        mock_run_command.assert_called_once_with(*command)
        self.assertEqual(output, powertek_module.PowertekState.ON)

    def test_run_process_crashes_on_external_process_error(self):
        driver = powertek_module.PowertekPowerDriver()
        self.patch_run_command(returncode=1)
        self.assertRaises(
            PowerActionError, driver.run_process, factory.make_name("command")
        )

    def test_run_process_crashes_on_no_power_state_match_found(self):
        driver = powertek_module.PowertekPowerDriver()
        self.patch_run_command(stdout="Error")
        self.assertRaises(
            PowerActionError, driver.run_process, factory.make_name("command")
        )

    def test_power_on_calls_run_process(self):
        driver = powertek_module.PowertekPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context(
            pdu_version=powertek_module.PowertekPDVersion.VERSION_1
        )
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "off"
        mock_run_process = self.patch(driver, "run_process")
        driver.power_on(system_id, context)

        mock_power_query.assert_called_once_with(system_id, context)
        command = (
            ["snmpset"]
            + powertek_module._get_common_args(context, is_query=False)
            + ["i", "2"]
        )
        mock_run_process.assert_called_once_with(*command)

    def test_power_off_calls_run_process(self):
        driver = powertek_module.PowertekPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context(
            pdu_version=powertek_module.PowertekPDVersion.VERSION_1
        )
        mock_run_process = self.patch(driver, "run_process")
        driver.power_off(system_id, context)
        command = (
            ["snmpset"]
            + powertek_module._get_common_args(context, is_query=False)
            + ["i", "4"]
        )
        mock_run_process.assert_called_once_with(*command)

    def test_power_off_calls_run_process_for_v2(self):
        driver = powertek_module.PowertekPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context(
            pdu_version=powertek_module.PowertekPDVersion.VERSION_2
        )
        mock_run_process = self.patch(driver, "run_process")
        driver.power_off(system_id, context)
        command = (
            ["snmpset"]
            + powertek_module._get_common_args(context, is_query=False)
            + ["i", "1"]
        )
        mock_run_process.assert_called_once_with(*command)

    def test_power_query_returns_power_state_on(self):
        driver = powertek_module.PowertekPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = powertek_module.PowertekState.ON
        result = driver.power_query(system_id, context)
        command = ["snmpget"] + powertek_module._get_common_args(
            context, is_query=True
        )
        mock_run_process.assert_called_once_with(*command)
        self.assertEqual(result, "on")

    def test_power_query_returns_power_state_off(self):
        driver = powertek_module.PowertekPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = "1"
        result = driver.power_query(system_id, context)
        command = ["snmpget"] + powertek_module._get_common_args(
            context, is_query=True
        )
        mock_run_process.assert_called_once_with(*command)
        self.assertEqual(result, "off")

    def test_power_query_returns_off_for_unknown_power_state(self):
        driver = powertek_module.PowertekPowerDriver()
        system_id = factory.make_name("system_id")
        context = self.make_context()
        mock_run_process = self.patch(driver, "run_process")
        mock_run_process.return_value = "99"
        result = driver.power_query(system_id, context)
        self.assertEqual(result, "off")

    def test_common_args_uses_configured_community(self):
        context = self.make_context()
        context["power_community"] = "maas-write"
        self.assertEqual(
            [
                "-c",
                "maas-write",
                "-v1",
                context["power_address"],
                self.expected_v1_query_oid(context),
            ],
            powertek_module._get_common_args(context, is_query=True),
        )

    def test_common_args_uses_v1_control_oid(self):
        context = self.make_context(
            pdu_version=powertek_module.PowertekPDVersion.VERSION_1,
            outlet=7,
            pdu_number="3",
        )
        self.assertEqual(
            [
                "-c",
                "private",
                "-v1",
                context["power_address"],
                self.expected_v1_control_oid(context),
            ],
            powertek_module._get_common_args(context, is_query=False),
        )

    def test_common_args_uses_v2_oid(self):
        context = self.make_context(
            pdu_version=powertek_module.PowertekPDVersion.VERSION_2,
            outlet=9,
            pdu_number="5",
        )
        self.assertEqual(
            [
                "-c",
                "private",
                "-v1",
                context["power_address"],
                self.expected_v2_oid(context),
            ],
            powertek_module._get_common_args(context, is_query=True),
        )

    def test_common_args_invalid_version_raises_error(self):
        context = self.make_context()
        context["pdu_version"] = "3"
        self.assertRaises(
            PowerActionError,
            powertek_module._get_common_args,
            context,
            True,
        )