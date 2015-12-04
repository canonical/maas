# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.mscm`."""

__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.hardware.tests.test_mscm import make_node_id
from provisioningserver.drivers.power import mscm as mscm_module
from provisioningserver.drivers.power.mscm import (
    extract_mscm_parameters,
    MSCMPowerDriver,
)
from testtools.matchers import Equals


class TestMSCMPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = mscm_module.MSCMPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name('system_id')
        host = factory.make_name('power_address')
        username = factory.make_name('power_user')
        password = factory.make_name('power_pass')
        node_id = make_node_id()
        context = {
            'system_id': system_id,
            'power_address': host,
            'power_user': username,
            'power_pass': password,
            'node_id': node_id,
        }
        return system_id, host, username, password, node_id, context

    def test_extract_mscm_parameters_extracts_parameters(self):
        system_id, host, username, password, node_id, context = (
            self.make_parameters())

        self.assertItemsEqual(
            (host, username, password, node_id),
            extract_mscm_parameters(context))

    def test_power_on_calls_power_control_mscm(self):
        system_id, host, username, password, node_id, context = (
            self.make_parameters())
        mscm_power_driver = MSCMPowerDriver()
        power_control_mscm = self.patch(
            mscm_module, 'power_control_mscm')
        mscm_power_driver.power_on(system_id, context)

        self.assertThat(
            power_control_mscm, MockCalledOnceWith(
                host, username, password, node_id, power_change='on'))

    def test_power_off_calls_power_control_mscm(self):
        system_id, host, username, password, node_id, context = (
            self.make_parameters())
        mscm_power_driver = MSCMPowerDriver()
        power_control_mscm = self.patch(
            mscm_module, 'power_control_mscm')
        mscm_power_driver.power_off(system_id, context)

        self.assertThat(
            power_control_mscm, MockCalledOnceWith(
                host, username, password, node_id, power_change='off'))

    def test_power_query_calls_power_state_mscm(self):
        system_id, host, username, password, node_id, context = (
            self.make_parameters())
        mscm_power_driver = MSCMPowerDriver()
        power_state_mscm = self.patch(
            mscm_module, 'power_state_mscm')
        power_state_mscm.return_value = 'off'
        expected_result = mscm_power_driver.power_query(system_id, context)

        self.expectThat(
            power_state_mscm, MockCalledOnceWith(
                host, username, password, node_id))
        self.expectThat(expected_result, Equals('off'))
