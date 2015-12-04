# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.apc``."""

__all__ = []

from random import randint
from subprocess import PIPE

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver.drivers.hardware import apc as apc_module
from provisioningserver.drivers.hardware.apc import (
    APCException,
    APCSNMP,
    power_control_apc,
    power_state_apc,
)
from provisioningserver.utils.shell import ExternalProcessError
from testtools.matchers import Equals


COMMON_ARGS = '-c private -v1 %s .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%s'
COMMON_OUTPUT = 'iso.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%s = INTEGER: 1\n'


class TestAPCSNMP(MAASTestCase):
    """Test for `APCSNMP`."""

    def patch_popen(self, return_value=(None, None), returncode=0):
        process = Mock()
        process.returncode = returncode
        process.communicate = Mock(return_value=return_value)
        self.patch(apc_module, 'Popen', Mock(return_value=process))
        return process

    def test_run_process_calls_command(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        command = 'snmpget ' + COMMON_ARGS % (ip, outlet)
        return_value = ((COMMON_OUTPUT % outlet), 'error_output')
        self.patch_popen(return_value)
        apc = APCSNMP()

        apc.run_process(command)
        self.assertThat(
            apc_module.Popen, MockCalledOnceWith(command.split(), stdout=PIPE))

    def test_run_process_returns_result(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        command = 'snmpget ' + COMMON_ARGS % (ip, outlet)
        return_value = ((COMMON_OUTPUT % outlet), 'error_output')
        self.patch_popen(return_value)
        apc = APCSNMP()

        result = apc.run_process(command)
        self.assertEqual(result, '1')

    def test_run_process_catches_failures(self):
        apc = APCSNMP()
        self.patch_popen(returncode=1)
        self.assertRaises(
            ExternalProcessError,
            apc.run_process, factory.make_name('command'))

    def test_power_off_outlet_calls_run_process(self):
        apc = APCSNMP()
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        command = 'snmpset ' + COMMON_ARGS % (ip, outlet) + ' i 2'
        run_process = self.patch(apc, 'run_process')

        apc.power_off_outlet(ip, outlet)
        self.assertThat(run_process, MockCalledOnceWith(command))

    def test_power_on_outlet_calls_run_process(self):
        apc = APCSNMP()
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        power_on_delay = 0
        command = 'snmpset ' + COMMON_ARGS % (ip, outlet) + ' i 1'
        power_off_outlet = self.patch(apc, 'power_off_outlet')
        run_process = self.patch(apc, 'run_process')

        apc.power_on_outlet(ip, outlet, power_on_delay)
        self.expectThat(power_off_outlet, MockCalledOnceWith(ip, outlet))
        self.expectThat(run_process, MockCalledOnceWith(command))

    def test_get_power_state_of_outlet_calls_run_process(self):
        apc = APCSNMP()
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        command = 'snmpget ' + COMMON_ARGS % (ip, outlet)
        run_process = self.patch(apc, 'run_process')

        apc.get_power_state_of_outlet(ip, outlet)
        self.assertThat(run_process, MockCalledOnceWith(command))


class TestAPCPowerControl(MAASTestCase):
    """Tests for `power_control_apc`."""

    def test__errors_on_unknown_power_change(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        power_change = factory.make_name('error')
        power_on_delay = 0
        self.assertRaises(
            AssertionError, power_control_apc, ip,
            outlet, power_change, power_on_delay)

    def test___power_change_on(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        power_change = 'on'
        power_on_delay = 0
        power_on_outlet = self.patch(APCSNMP, 'power_on_outlet')

        power_control_apc(ip, outlet, power_change, power_on_delay)
        self.assertThat(
            power_on_outlet, MockCalledOnceWith(
                ip, outlet, float(power_on_delay)))

    def test___power_change_off(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        power_change = 'off'
        power_on_delay = 0
        power_off_outlet = self.patch(APCSNMP, 'power_off_outlet')

        power_control_apc(ip, outlet, power_change, power_on_delay)
        self.assertThat(power_off_outlet, MockCalledOnceWith(ip, outlet))


class TestAPCPowerState(MAASTestCase):
    """Tests for `power_control_state`."""

    def test__gets_power_off_state(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        get_power_state_of_outlet = self.patch(
            APCSNMP, 'get_power_state_of_outlet', Mock(return_value='2'))

        power_state = power_state_apc(ip, outlet)
        self.expectThat(
            get_power_state_of_outlet, MockCalledOnceWith(ip, outlet))
        self.expectThat(power_state, Equals('off'))

    def test__gets_power_on_state(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        get_power_state_of_outlet = self.patch(
            APCSNMP, 'get_power_state_of_outlet', Mock(return_value='1'))

        power_state = power_state_apc(ip, outlet)
        self.expectThat(
            get_power_state_of_outlet, MockCalledOnceWith(ip, outlet))
        self.expectThat(power_state, Equals('on'))

    def test__errors_on_unknown_state(self):
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        get_power_state_of_outlet = self.patch(
            APCSNMP, 'get_power_state_of_outlet', Mock(return_value='error'))

        self.assertRaises(APCException, power_state_apc, ip, outlet)
        self.expectThat(
            get_power_state_of_outlet, MockCalledOnceWith(ip, outlet))
