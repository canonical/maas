# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.hmc``."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import choice
from StringIO import StringIO

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver.drivers.hardware.hmc import (
    HMC,
    HMCException,
    HMCState,
    power_control_hmc,
    power_state_hmc,
)
from testtools.matchers import Equals


def make_hmc_params():
    """Make parameters for HMC."""
    ip = factory.make_ipv4_address()
    username = factory.make_name('user')
    password = factory.make_name('password')
    server_name = factory.make_name('server_name')
    lpar = factory.make_name('lpar')
    return ip, username, password, server_name, lpar


def make_hmc_api():
    """Make a HMC object with randomized parameters."""
    ip, username, password, _, _ = make_hmc_params()
    return HMC(ip, username, password)


class TestHMC(MAASTestCase):
    """Tests for `HMC`."""

    def test_run_cli_command_returns_output(self):
        api = make_hmc_api()
        command = factory.make_name('command')
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api._run_cli_command(command)
        self.expectThat(expected, Equals(output))
        self.expectThat(ssh_mock.exec_command, MockCalledOnceWith(command))

    def test_run_cli_command_connects_and_closes_ssh_client(self):
        api = make_hmc_api()
        ssh_mock = self.patch(api, '_ssh')
        ssh_mock.exec_command = Mock(return_value=factory.make_streams())
        api._run_cli_command(factory.make_name('command'))
        self.expectThat(
            ssh_mock.connect,
            MockCalledOnceWith(
                api.ip, username=api.username, password=api.password))
        self.expectThat(ssh_mock.close, MockCalledOnceWith())

    def test_run_cli_command_closes_when_exception_raised(self):
        api = make_hmc_api()
        ssh_mock = self.patch(api, '_ssh')
        exception_type = factory.make_exception_type()
        ssh_mock.exec_command = Mock(side_effect=exception_type)
        command = factory.make_name('command')
        self.assertRaises(exception_type, api._run_cli_command, command)
        self.expectThat(ssh_mock.close, MockCalledOnceWith())

    def test_get_lpar_power_state_gets_power_state(self):
        api = make_hmc_api()
        server_name = factory.make_name('server_name')
        lpar = factory.make_name('lpar')
        state = factory.make_name('state')
        expected = '%s:%s\n' % (lpar, state)
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        output = api.get_lpar_power_state(server_name, lpar)
        command = "lssyscfg -m %s -r lpar -F name:state" % server_name

        self.expectThat(
            expected.split('%s:' % lpar)[1].split('\n')[0], Equals(output))
        self.expectThat(cli_mock, MockCalledOnceWith(command))

    def test_power_lpar_on_returns_expected_output(self):
        api = make_hmc_api()
        server_name = factory.make_name('server_name')
        lpar = factory.make_name('lpar')
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api.power_lpar_on(server_name, lpar)
        command = ("chsysstate -r lpar -m %s -o on -n %s "
                   "--bootstring network-all" % (server_name, lpar))

        self.expectThat(expected, Equals(output))
        self.expectThat(
            ssh_mock.exec_command, MockCalledOnceWith(command))

    def test_power_lpar_off_returns_expected_output(self):
        api = make_hmc_api()
        server_name = factory.make_name('server_name')
        lpar = factory.make_name('lpar')
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api.power_lpar_off(server_name, lpar)
        command = ("chsysstate -r lpar -m %s -o shutdown -n %s --immed"
                   % (server_name, lpar))

        self.expectThat(expected, Equals(output))
        self.expectThat(
            ssh_mock.exec_command, MockCalledOnceWith(command))


class TestHMCPowerControl(MAASTestCase):
    """Tests for `power_control_hmc`."""

    def test_power_control_error_on_unknown_power_change(self):
        ip, username, password, server_name, lpar = make_hmc_params()
        power_change = factory.make_name('error')
        self.assertRaises(
            HMCException, power_control_hmc, ip, username,
            password, server_name, lpar, power_change)

    def test_power_control_power_change_on_power_state_on(self):
        # power_change and current power_state are both 'on'
        ip, username, password, server_name, lpar = make_hmc_params()
        power_state_mock = self.patch(HMC, 'get_lpar_power_state')
        power_state_mock.return_value = choice(HMCState.ON)
        power_lpar_off_mock = self.patch(HMC, 'power_lpar_off')
        power_lpar_on_mock = self.patch(HMC, 'power_lpar_on')

        power_control_hmc(ip, username, password, server_name,
                          lpar, power_change='on')
        self.expectThat(
            power_state_mock, MockCalledOnceWith(server_name, lpar))
        self.expectThat(
            power_lpar_off_mock, MockCalledOnceWith(server_name, lpar))
        self.expectThat(
            power_lpar_on_mock, MockCalledOnceWith(server_name, lpar))

    def test_power_control_power_change_on_power_state_off(self):
        # power_change is 'on' and current power_state is 'off'
        ip, username, password, server_name, lpar = make_hmc_params()
        power_state_mock = self.patch(HMC, 'get_lpar_power_state')
        power_state_mock.return_value = HMCState.OFF
        power_lpar_on_mock = self.patch(HMC, 'power_lpar_on')

        power_control_hmc(ip, username, password, server_name,
                          lpar, power_change='on')
        self.expectThat(
            power_state_mock, MockCalledOnceWith(server_name, lpar))
        self.expectThat(
            power_lpar_on_mock, MockCalledOnceWith(server_name, lpar))

    def test_power_control_power_change_off_power_state_on(self):
        # power_change is 'off' and current power_state is 'on'
        ip, username, password, server_name, lpar = make_hmc_params()
        power_lpar_off_mock = self.patch(HMC, 'power_lpar_off')

        power_control_hmc(ip, username, password, server_name,
                          lpar, power_change='off')
        self.expectThat(
            power_lpar_off_mock, MockCalledOnceWith(server_name, lpar))


class TestHMCPowerState(MAASTestCase):
    """Tests for `power_state_hmc`."""

    def test_power_state_failed_to_get_state(self):
        ip, username, password, server_name, lpar = make_hmc_params()
        power_state_mock = self.patch(HMC, 'get_lpar_power_state')
        power_state_mock.side_effect = HMCException('error')
        self.assertRaises(
            HMCException, power_state_hmc, ip, username,
            password, server_name, lpar)

    def test_power_state_get_off(self):
        ip, username, password, server_name, lpar = make_hmc_params()
        power_state_mock = self.patch(HMC, 'get_lpar_power_state')
        power_state_mock.return_value = choice(HMCState.OFF)
        self.assertThat(
            power_state_hmc(ip, username, password, server_name, lpar),
            Equals('off'))

    def test_power_state_get_on(self):
        ip, username, password, server_name, lpar = make_hmc_params()
        power_state_mock = self.patch(HMC, 'get_lpar_power_state')
        power_state_mock.return_value = choice(HMCState.ON)
        self.assertThat(
            power_state_hmc(ip, username, password, server_name, lpar),
            Equals('on'))

    def test_power_state_error_on_unknown_state(self):
        ip, username, password, server_name, lpar = make_hmc_params()
        power_state_mock = self.patch(HMC, 'get_lpar_power_state')
        power_state_mock.return_value = factory.make_name('error')
        self.assertRaises(
            HMCException, power_state_hmc, ip, username,
            password, server_name, lpar)
