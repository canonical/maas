# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.wedge`."""

from io import BytesIO
from random import choice
from socket import error as SOCKETError
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis.strategies import sampled_from
from paramiko import SSHException

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerFatalError,
)
from provisioningserver.drivers.power import wedge as wedge_module
from provisioningserver.drivers.power.wedge import WedgePowerDriver, WedgeState


def make_context():
    """Make and return a power parameters context."""
    return {
        "power_address": factory.make_name("power_address"),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
    }


class TestWedgePowerDriver(MAASTestCase):
    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = wedge_module.WedgePowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_run_wedge_command_returns_command_output(self):
        driver = WedgePowerDriver()
        command = factory.make_name("command")
        context = make_context()
        mock_ssh_client = Mock()
        expected = factory.make_name("output").encode("utf-8")
        stdout = BytesIO(expected)
        streams = factory.make_streams(stdout=stdout)
        mock_ssh_client.exec_command = Mock(return_value=streams)
        self.patch(wedge_module, "connect_ssh").return_value = mock_ssh_client

        output = driver.run_wedge_command(command, **context)

        self.assertEqual(expected.decode("utf-8"), output)
        wedge_module.connect_ssh.assert_called_once_with(
            driver.name,
            context["power_address"],
            context["power_user"],
            context["power_pass"],
        )
        mock_ssh_client.exec_command.assert_called_once_with(command)

    def test_run_wedge_command_uses_fips_ssh_configuration(self):
        driver = WedgePowerDriver()
        command = factory.make_name("command")
        context = make_context()
        mock_ssh_client = Mock()
        expected = factory.make_name("output").encode("utf-8")
        stdout = BytesIO(expected)
        streams = factory.make_streams(stdout=stdout)
        mock_ssh_client.exec_command = Mock(return_value=streams)
        mock_connect_ssh = self.patch(wedge_module, "connect_ssh")
        mock_connect_ssh.return_value = mock_ssh_client
        self.patch(wedge_module, "is_fips_enabled").return_value = True

        output = driver.run_wedge_command(command, **context)

        self.assertEqual(expected.decode("utf-8"), output)
        mock_connect_ssh.assert_called_once_with(
            driver.name,
            context["power_address"],
            context["power_user"],
            context["power_pass"],
        )

    @settings(deadline=None)
    @given(sampled_from([SSHException, EOFError, SOCKETError]))
    def test_run_wedge_command_crashes_for_ssh_connection_error(self, error):
        driver = WedgePowerDriver()
        command = factory.make_name("command")
        context = make_context()
        mock_connect_ssh = self.patch(wedge_module, "connect_ssh")
        mock_connect_ssh.side_effect = error
        self.assertRaises(
            PowerConnError, driver.run_wedge_command, command, **context
        )

    def test_power_on_calls_run_wedge_command(self):
        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        power_query = self.patch(driver, "power_query")
        power_query.return_value = choice(WedgeState.ON)
        self.patch(driver, "power_off")
        run_wedge_command = self.patch(driver, "run_wedge_command")
        driver.power_on(system_id, context)
        run_wedge_command.assert_called_once_with(
            "/usr/local/bin/wedge_power.sh on", **context
        )

    def test_power_on_crashes_for_connection_error(self):
        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        power_query = self.patch(driver, "power_query")
        power_query.return_value = "off"
        run_wedge_command = self.patch(driver, "run_wedge_command")
        run_wedge_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_on, system_id, context
        )

    def test_power_off_calls_run_wedge_command(self):
        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_wedge_command = self.patch(driver, "run_wedge_command")
        driver.power_off(system_id, context)
        run_wedge_command.assert_called_once_with(
            "/usr/local/bin/wedge_power.sh off", **context
        )

    def test_power_off_crashes_for_connection_error(self):
        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_wedge_command = self.patch(driver, "run_wedge_command")
        run_wedge_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_off, system_id, context
        )

    @given(sampled_from(WedgeState.ON + WedgeState.OFF))
    @settings(deadline=None)
    def test_power_query_returns_power_state(self, power_state):
        def get_wedge_state(power_state):
            if power_state in WedgeState.OFF:
                return "off"
            elif power_state in WedgeState.ON:
                return "on"

        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_wedge_command = self.patch(driver, "run_wedge_command")
        run_wedge_command.return_value = power_state
        output = driver.power_query(system_id, context)
        self.assertEqual(get_wedge_state(power_state), output)

    def test_power_query_crashes_for_connection_error(self):
        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_wedge_command = self.patch(driver, "run_wedge_command")
        run_wedge_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_query, system_id, context
        )

    def test_power_query_crashes_when_unable_to_find_match(self):
        driver = WedgePowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_wedge_command = self.patch(driver, "run_wedge_command")
        run_wedge_command.return_value = "Rubbish"
        self.assertRaises(
            PowerFatalError, driver.power_query, system_id, context
        )
