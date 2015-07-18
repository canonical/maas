# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.seamicro`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import choice

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import (
    PowerFatalError,
    seamicro as seamicro_module,
)
from provisioningserver.drivers.power.seamicro import (
    extract_seamicro_parameters,
    SeaMicroPowerDriver,
)
from provisioningserver.utils.shell import ExternalProcessError
from testtools.matchers import Equals


class TestSeaMicroPowerDriver(MAASTestCase):

    def make_parameters(self):
        ip = factory.make_name('power_address')
        username = factory.make_name('power_user')
        password = factory.make_name('power_pass')
        server_id = factory.make_name('system_id')
        params = {
            'power_address': ip,
            'power_user': username,
            'power_pass': password,
            'system_id': server_id,
        }
        return ip, username, password, server_id, params

    def test_extract_seamicro_parameters_extracts_parameters(self):
        ip, username, password, server_id, params = self.make_parameters()
        power_control = choice(['ipmi', 'restapi', 'restapi2'])
        params['power_control'] = power_control

        self.assertItemsEqual(
            (ip, username, password, server_id, power_control),
            extract_seamicro_parameters(params))

    def test__power_control_seamicro15k_ipmi_calls_call_and_check(self):
        ip, username, password, server_id, _ = self.make_parameters()
        power_change = choice(['on', 'off'])
        seamicro_power_driver = SeaMicroPowerDriver()
        call_and_check_mock = self.patch(seamicro_module, 'call_and_check')
        seamicro_power_driver._power_control_seamicro15k_ipmi(
            ip, username, password, server_id, power_change)
        power_mode = 1 if power_change == 'on' else 6

        self.assertThat(
            call_and_check_mock, MockCalledOnceWith([
                'ipmitool', '-I', 'lanplus', '-H', ip, '-U', username,
                '-P', password, 'raw', '0x2E', '1', '0x00', '0x7d',
                '0xab', power_mode, '0', server_id,
            ]))

    def test__power_control_seamicro15k_ipmi_raises_PowerFatalError(self):
        ip, username, password, server_id, _ = self.make_parameters()
        power_change = choice(['on', 'off'])
        seamicro_power_driver = SeaMicroPowerDriver()
        call_and_check_mock = self.patch(seamicro_module, 'call_and_check')
        call_and_check_mock.side_effect = (
            ExternalProcessError(1, "ipmitool something"))

        self.assertRaises(
            PowerFatalError,
            seamicro_power_driver._power_control_seamicro15k_ipmi,
            ip, username, password, server_id, power_change)

    def test__power_calls__power_control_seamicro15k_ipmi(self):
        ip, username, password, server_id, params = self.make_parameters()
        params['power_control'] = 'ipmi'
        power_change = choice(['on', 'off'])
        seamicro_power_driver = SeaMicroPowerDriver()
        _power_control_seamicro15k_ipmi_mock = self.patch(
            seamicro_power_driver, '_power_control_seamicro15k_ipmi')
        seamicro_power_driver._power(power_change, **params)

        self.assertThat(
            _power_control_seamicro15k_ipmi_mock, MockCalledOnceWith(
                ip, username, password, server_id, power_change=power_change))

    def test__power_calls_power_control_seamicro15k_v09(self):
        ip, username, password, server_id, params = self.make_parameters()
        params['power_control'] = 'restapi'
        power_change = choice(['on', 'off'])
        seamicro_power_driver = SeaMicroPowerDriver()
        power_control_seamicro15k_v09_mock = self.patch(
            seamicro_module, 'power_control_seamicro15k_v09')
        seamicro_power_driver._power(power_change, **params)

        self.assertThat(
            power_control_seamicro15k_v09_mock, MockCalledOnceWith(
                ip, username, password, server_id, power_change=power_change))

    def test__power_calls_power_control_seamicro15k_v2(self):
        ip, username, password, server_id, params = self.make_parameters()
        params['power_control'] = 'restapi2'
        power_change = choice(['on', 'off'])
        seamicro_power_driver = SeaMicroPowerDriver()
        power_control_seamicro15k_v2_mock = self.patch(
            seamicro_module, 'power_control_seamicro15k_v2')
        seamicro_power_driver._power(power_change, **params)

        self.assertThat(
            power_control_seamicro15k_v2_mock, MockCalledOnceWith(
                ip, username, password, server_id, power_change=power_change))

    def test_power_on_calls_power(self):
        _, _, _, _, params = self.make_parameters()
        params['power_control'] = factory.make_name('power_control')
        seamicro_power_driver = SeaMicroPowerDriver()
        power_mock = self.patch(seamicro_power_driver, '_power')
        seamicro_power_driver.power_on(**params)
        del params['system_id']

        self.assertThat(
            power_mock, MockCalledOnceWith('on', **params))

    def test_power_off_calls_power(self):
        _, _, _, _, params = self.make_parameters()
        params['power_control'] = factory.make_name('power_control')
        seamicro_power_driver = SeaMicroPowerDriver()
        power_mock = self.patch(seamicro_power_driver, '_power')
        seamicro_power_driver.power_off(**params)
        del params['system_id']

        self.assertThat(
            power_mock, MockCalledOnceWith('off', **params))

    def test_power_query_calls_power_query_seamicro15k_v2(self):
        ip, username, password, server_id, params = self.make_parameters()
        params['power_control'] = 'restapi2'
        seamicro_power_driver = SeaMicroPowerDriver()
        power_query_seamicro15k_v2_mock = self.patch(
            seamicro_module, 'power_query_seamicro15k_v2')
        power_query_seamicro15k_v2_mock.return_value = 'on'
        power_state = seamicro_power_driver.power_query(**params)

        self.expectThat(
            power_query_seamicro15k_v2_mock, MockCalledOnceWith(
                ip, username, password, server_id))
        self.expectThat(power_state, Equals('on'))

    def test_power_query_returns_unknown_if_not_restapi2(self):
        ip, username, password, server_id, params = self.make_parameters()
        params['power_control'] = factory.make_name('power_control')
        seamicro_power_driver = SeaMicroPowerDriver()
        power_state = seamicro_power_driver.power_query(**params)

        self.assertThat(power_state, Equals('unknown'))
