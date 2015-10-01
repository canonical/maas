# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.msftocs`."""

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
from provisioningserver.drivers.power import msftocs as msftocs_module
from provisioningserver.drivers.power.msftocs import (
    extract_msftocs_parameters,
    MicrosoftOCSPowerDriver,
)
from testtools.matchers import Equals


class TestMicrosoftOCSPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = msftocs_module.MicrosoftOCSPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name('system_id')
        ip = factory.make_name('power_address')
        port = factory.make_name('power_port')
        username = factory.make_name('power_user')
        password = factory.make_name('power_pass')
        blade_id = factory.make_name('blade_id')
        params = {
            'system_id': system_id,
            'power_address': ip,
            'power_port': port,
            'power_user': username,
            'power_pass': password,
            'blade_id': blade_id,
        }
        return system_id, ip, port, username, password, blade_id, params

    def test_extract_msftocs_parameters_extracts_parameters(self):
        system_id, ip, port, username, password, blade_id, params = (
            self.make_parameters())

        self.assertItemsEqual(
            (ip, port, username, password, blade_id),
            extract_msftocs_parameters(params))

    def test_power_on_calls_power_control_msftocs(self):
        power_change = 'on'
        system_id, ip, port, username, password, blade_id, params = (
            self.make_parameters())
        msftocs_power_driver = MicrosoftOCSPowerDriver()
        power_control_msftocs = self.patch(
            msftocs_module, 'power_control_msftocs')
        msftocs_power_driver.power_on(**params)

        self.assertThat(
            power_control_msftocs, MockCalledOnceWith(
                ip, port, username, password, power_change))

    def test_power_off_calls_power_control_msftocs(self):
        power_change = 'off'
        system_id, ip, port, username, password, blade_id, params = (
            self.make_parameters())
        msftocs_power_driver = MicrosoftOCSPowerDriver()
        power_control_msftocs = self.patch(
            msftocs_module, 'power_control_msftocs')
        msftocs_power_driver.power_off(**params)

        self.assertThat(
            power_control_msftocs, MockCalledOnceWith(
                ip, port, username, password, power_change))

    def test_power_query_calls_power_state_msftocs(self):
        system_id, ip, port, username, password, blade_id, params = (
            self.make_parameters())
        msftocs_power_driver = MicrosoftOCSPowerDriver()
        power_state_msftocs = self.patch(
            msftocs_module, 'power_state_msftocs')
        power_state_msftocs.return_value = 'off'
        expected_result = msftocs_power_driver.power_query(**params)

        self.expectThat(
            power_state_msftocs, MockCalledOnceWith(
                ip, port, username, password, blade_id))
        self.expectThat(expected_result, Equals('off'))
