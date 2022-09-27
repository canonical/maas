# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.hmc`."""


from io import BytesIO
from random import choice
from socket import error as SOCKETError
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis.strategies import sampled_from
from paramiko import SSHException
from testtools.matchers import Equals

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerFatalError,
)
from provisioningserver.drivers.power import hmc as hmc_module
from provisioningserver.drivers.power.hmc import HMCPowerDriver, HMCState


def make_context():
    """Make and return a power parameters context."""
    return {
        "power_address": factory.make_name("power_address"),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
        "server_name": factory.make_name("server_name"),
        "lpar": factory.make_name("lpar"),
    }


class TestHMCPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = hmc_module.HMCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_run_hmc_command_returns_command_output(self):
        driver = HMCPowerDriver()
        command = factory.make_name("command")
        context = make_context()
        SSHClient = self.patch(hmc_module, "SSHClient")
        AutoAddPolicy = self.patch(hmc_module, "AutoAddPolicy")
        ssh_client = SSHClient.return_value
        expected = factory.make_name("output").encode("utf-8")
        stdout = BytesIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_client.exec_command = Mock(return_value=streams)
        output = driver.run_hmc_command(command, **context)

        self.expectThat(expected.decode("utf-8"), Equals(output))
        self.expectThat(SSHClient, MockCalledOnceWith())
        self.expectThat(
            ssh_client.set_missing_host_key_policy,
            MockCalledOnceWith(AutoAddPolicy.return_value),
        )
        self.expectThat(
            ssh_client.connect,
            MockCalledOnceWith(
                context["power_address"],
                username=context["power_user"],
                password=context["power_pass"],
            ),
        )
        self.expectThat(ssh_client.exec_command, MockCalledOnceWith(command))

    @settings(deadline=None)
    @given(sampled_from([SSHException, EOFError, SOCKETError]))
    def test_run_hmc_command_crashes_for_ssh_connection_error(self, error):
        driver = HMCPowerDriver()
        command = factory.make_name("command")
        context = make_context()
        self.patch(hmc_module, "AutoAddPolicy")
        SSHClient = self.patch(hmc_module, "SSHClient")
        ssh_client = SSHClient.return_value
        ssh_client.connect.side_effect = error
        self.assertRaises(
            PowerConnError, driver.run_hmc_command, command, **context
        )

    def test_power_on_calls_run_hmc_command(self):
        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        power_query = self.patch(driver, "power_query")
        power_query.return_value = choice(HMCState.ON)
        self.patch(driver, "power_off")
        run_hmc_command = self.patch(driver, "run_hmc_command")
        driver.power_on(system_id, context)
        self.assertThat(
            run_hmc_command,
            MockCalledOnceWith(
                "chsysstate -r lpar -m %s -o on -n %s --bootstring network-all"
                % (context["server_name"], context["lpar"]),
                **context
            ),
        )

    def test_power_on_crashes_for_connection_error(self):
        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        power_query = self.patch(driver, "power_query")
        power_query.return_value = "off"
        run_hmc_command = self.patch(driver, "run_hmc_command")
        run_hmc_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_on, system_id, context
        )

    def test_power_off_calls_run_hmc_command(self):
        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_hmc_command = self.patch(driver, "run_hmc_command")
        driver.power_off(system_id, context)
        self.assertThat(
            run_hmc_command,
            MockCalledOnceWith(
                "chsysstate -r lpar -m %s -o shutdown -n %s --immed"
                % (context["server_name"], context["lpar"]),
                **context
            ),
        )

    def test_power_off_crashes_for_connection_error(self):
        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_hmc_command = self.patch(driver, "run_hmc_command")
        run_hmc_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_off, system_id, context
        )

    @given(sampled_from(HMCState.ON + HMCState.OFF))
    @settings(deadline=None)
    def test_power_query_returns_power_state(self, power_state):
        def get_hmc_state(power_state):
            if power_state in HMCState.OFF:
                return "off"
            elif power_state in HMCState.ON:
                return "on"

        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_hmc_command = self.patch(driver, "run_hmc_command")
        run_hmc_command.return_value = power_state
        output = driver.power_query(system_id, context)
        self.assertEqual(get_hmc_state(power_state), output)

    def test_power_query_crashes_for_connection_error(self):
        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_hmc_command = self.patch(driver, "run_hmc_command")
        run_hmc_command.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_query, system_id, context
        )

    def test_power_query_crashes_when_unable_to_find_match(self):
        driver = HMCPowerDriver()
        system_id = factory.make_name("system_id")
        context = make_context()
        run_hmc_command = self.patch(driver, "run_hmc_command")
        run_hmc_command.return_value = "Rubbish"
        self.assertRaises(
            PowerFatalError, driver.power_query, system_id, context
        )
