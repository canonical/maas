# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.apc`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import apc as apc_module
from provisioningserver.drivers.power.apc import (
    APCPowerDriver,
    extract_apc_parameters,
)
from provisioningserver.utils.shell import has_command_available
from testtools.matchers import Equals


class TestAPCPowerDriver(MAASTestCase):

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

    def make_parameters(self):
        system_id = factory.make_name('system_id')
        ip = factory.make_ipv4_address()
        outlet = '%d' % randint(1, 16)
        power_on_delay = '%d' % randint(1, 5)
        params = {
            'system_id': system_id,
            'power_address': ip,
            'node_outlet': outlet,
            'power_on_delay': power_on_delay,
        }
        return system_id, ip, outlet, power_on_delay, params

    def test_extract_apc_parameters_extracts_parameters(self):
        system_id, ip, outlet, power_on_delay, params = self.make_parameters()

        self.assertItemsEqual(
            (ip, outlet, power_on_delay),
            extract_apc_parameters(params))

    def test_power_on_calls_power_control_apc(self):
        power_change = 'on'
        system_id, ip, outlet, power_on_delay, params = self.make_parameters()
        apc_power_driver = APCPowerDriver()
        power_control_apc = self.patch(
            apc_module, 'power_control_apc')
        apc_power_driver.power_on(**params)

        self.assertThat(
            power_control_apc, MockCalledOnceWith(
                ip, outlet, power_change, power_on_delay))

    def test_power_off_calls_power_control_apc(self):
        power_change = 'off'
        system_id, ip, outlet, power_on_delay, params = self.make_parameters()
        apc_power_driver = APCPowerDriver()
        power_control_apc = self.patch(
            apc_module, 'power_control_apc')
        apc_power_driver.power_off(**params)

        self.assertThat(
            power_control_apc, MockCalledOnceWith(
                ip, outlet, power_change, power_on_delay))

    def test_power_query_calls_power_state_apc(self):
        system_id, ip, outlet, power_on_delay, params = self.make_parameters()
        apc_power_driver = APCPowerDriver()
        power_state_apc = self.patch(
            apc_module, 'power_state_apc')
        power_state_apc.return_value = 'off'
        expected_result = apc_power_driver.power_query(**params)

        self.expectThat(
            power_state_apc, MockCalledOnceWith(ip, outlet))
        self.expectThat(expected_result, Equals('off'))
