# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.nova`."""

__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import nova as nova_module
from provisioningserver.drivers.power.nova import NovaPowerDriver
from testtools.matchers import Equals


class TestNovaPowerDriver(MAASTestCase):

    def test_missing_packages(self):
        driver = nova_module.NovaPowerDriver()
        mock = self.patch(driver, 'try_novaapi_import')
        mock.return_value = False
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(['python3-novaclient'], missing)

    def test_no_missing_packages(self):
        driver = nova_module.NovaPowerDriver()
        mock = self.patch(driver, 'try_novaapi_import')
        mock.return_value = True
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name('system_id')
        machine = factory.make_name('nova_id')
        tenant = factory.make_name('os_tenantname')
        username = factory.make_name('os_username')
        password = factory.make_name('os_password')
        authurl = 'http://%s' % (factory.make_name('os_authurl'))
        context = {
            'system_id': system_id,
            'nova_id': machine,
            'os_tenantname': tenant,
            'os_username': username,
            'os_password': password,
            'os_authurl': authurl,
        }
        return system_id, machine, tenant, username, password, authurl, context

    def test_power_on_calls_power_control_nova(self):
        system_id, machine, tenant, username, password, authurl, context = (
            self.make_parameters())
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, 'power_control_nova')
        nova_power_driver.power_on(system_id, context)

        self.assertThat(
            power_control_nova_mock, MockCalledOnceWith('on', **context))

    def test_power_off_calls_power_control_nova(self):
        system_id, machine, tenant, username, password, authurl, context = (
            self.make_parameters())
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, 'power_control_nova')
        nova_power_driver.power_off(system_id, context)

        self.assertThat(
            power_control_nova_mock, MockCalledOnceWith('off', **context))

    def test_power_query_calls_power_state_nova(self):
        system_id, machine, tenant, username, password, authurl, context = (
            self.make_parameters())
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, 'power_control_nova')
        power_control_nova_mock.return_value = 'off'
        expected_result = nova_power_driver.power_query(system_id, context)

        self.expectThat(
            power_control_nova_mock, MockCalledOnceWith('query', **context))
        self.expectThat(expected_result, Equals('off'))

    def make_parameters_v3(self):
        system_id = factory.make_name('system_id')
        machine = factory.make_name('nova_id')
        tenant = factory.make_name('os_tenantname')
        username = factory.make_name('os_username')
        password = factory.make_name('os_password')
        authurl = 'http://%s' % (factory.make_name('os_authurl'))
        user_domain_name = factory.make_name('user_domain_name')
        project_domain_name = factory.make_name('project_domain_name')
        context = {
            'system_id': system_id,
            'nova_id': machine,
            'os_tenantname': tenant,
            'os_username': username,
            'os_password': password,
            'os_authurl': authurl,
            'user_domain_name': user_domain_name,
            'project_domain_name': project_domain_name,
        }
        return system_id, machine, tenant, username, password,
               authurl, user_domain_name, project_domain_name, context

    def test_power_on_calls_power_control_nova_v3(self):
        system_id, machine, tenant, username, password, authurl,
            user_domain_name, project_domain_name, context = (
            self.make_parameters_v3())
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, 'power_control_nova')
        nova_power_driver.power_on(system_id, context)

        self.assertThat(
            power_control_nova_mock, MockCalledOnceWith('on', **context))

    def test_power_off_calls_power_control_nova_v3(self):
        system_id, machine, tenant, username, password, authurl,
            user_domain_name, project_domain_name, context = (
            self.make_parameters_v3())
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, 'power_control_nova')
        nova_power_driver.power_off(system_id, context)

        self.assertThat(
            power_control_nova_mock, MockCalledOnceWith('off', **context))

    def test_power_query_calls_power_state_nova_v3(self):
        system_id, machine, tenant, username, password, authurl,
            user_domain_name, project_domain_name, context = (
            self.make_parameters_v3())
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, 'power_control_nova')
        power_control_nova_mock.return_value = 'off'
        expected_result = nova_power_driver.power_query(system_id, context)

        self.expectThat(
            power_control_nova_mock, MockCalledOnceWith('query', **context))
        self.expectThat(expected_result, Equals('off'))
