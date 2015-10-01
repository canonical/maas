# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.hmc`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import hmc as hmc_module
from provisioningserver.drivers.power.hmc import (
    extract_hmc_parameters,
    HMCPowerDriver,
)
from provisioningserver.utils.shell import has_command_available
from testtools.matchers import Equals


class TestHMCPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = hmc_module.HMCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(['HMC Management Software'], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = hmc_module.HMCPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name('system_id')
        ip = factory.make_name('power_address')
        username = factory.make_name('power_user')
        password = factory.make_name('power_pass')
        server_name = factory.make_name('server_name')
        lpar = factory.make_name('lpar')
        params = {
            'system_id': system_id,
            'power_address': ip,
            'power_user': username,
            'power_pass': password,
            'server_name': server_name,
            'lpar': lpar,
        }
        return system_id, ip, username, password, server_name, lpar, params

    def test_extract_hmc_parameters_extracts_parameters(self):
        system_id, ip, username, password, server_name, lpar, params = (
            self.make_parameters())
        self.assertItemsEqual(
            (ip, username, password, server_name, lpar),
            extract_hmc_parameters(params))

    def test_power_on_calls_power_control_hmc(self):
        system_id, ip, username, password, server_name, lpar, params = (
            self.make_parameters())
        hmc_power_driver = HMCPowerDriver()
        power_control_hmc = self.patch(
            hmc_module, 'power_control_hmc')
        hmc_power_driver.power_on(**params)

        self.assertThat(
            power_control_hmc, MockCalledOnceWith(
                ip, username, password, server_name, lpar, power_change='on'))

    def test_power_off_calls_power_control_hmc(self):
        system_id, ip, username, password, server_name, lpar, params = (
            self.make_parameters())
        hmc_power_driver = HMCPowerDriver()
        power_control_hmc = self.patch(
            hmc_module, 'power_control_hmc')
        hmc_power_driver.power_off(**params)

        self.assertThat(
            power_control_hmc, MockCalledOnceWith(
                ip, username, password, server_name, lpar, power_change='off'))

    def test_power_query_calls_power_state_hmc(self):
        system_id, ip, username, password, server_name, lpar, params = (
            self.make_parameters())
        hmc_power_driver = HMCPowerDriver()
        power_state_hmc = self.patch(
            hmc_module, 'power_state_hmc')
        power_state_hmc.return_value = 'off'
        expected_result = hmc_power_driver.power_query(**params)

        self.expectThat(
            power_state_hmc, MockCalledOnceWith(
                ip, username, password, server_name, lpar))
        self.expectThat(expected_result, Equals('off'))
