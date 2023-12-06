# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.nova`."""


from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import nova as nova_module
from provisioningserver.drivers.power.nova import NovaPowerDriver


class TestNovaPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        driver = nova_module.NovaPowerDriver()
        mock = self.patch(driver, "try_novaapi_import")
        mock.return_value = False
        missing = driver.detect_missing_packages()
        self.assertEqual(["python3-novaclient"], missing)

    def test_no_missing_packages(self):
        driver = nova_module.NovaPowerDriver()
        mock = self.patch(driver, "try_novaapi_import")
        mock.return_value = True
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name("system_id")
        machine = factory.make_name("nova_id")
        tenant = factory.make_name("os_tenantname")
        username = factory.make_name("os_username")
        password = factory.make_name("os_password")
        authurl = "http://%s" % (factory.make_name("os_authurl"))
        context = {
            "system_id": system_id,
            "nova_id": machine,
            "os_tenantname": tenant,
            "os_username": username,
            "os_password": password,
            "os_authurl": authurl,
        }
        return system_id, machine, tenant, username, password, authurl, context

    def test_power_on_calls_power_control_nova(self):
        (
            system_id,
            machine,
            tenant,
            username,
            password,
            authurl,
            context,
        ) = self.make_parameters()
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, "power_control_nova"
        )
        nova_power_driver.power_on(system_id, context)

        power_control_nova_mock.assert_called_once_with("on", **context)

    def test_power_off_calls_power_control_nova(self):
        (
            system_id,
            machine,
            tenant,
            username,
            password,
            authurl,
            context,
        ) = self.make_parameters()
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, "power_control_nova"
        )
        nova_power_driver.power_off(system_id, context)

        power_control_nova_mock.assert_called_once_with("off", **context)

    def test_power_query_calls_power_state_nova(self):
        (
            system_id,
            machine,
            tenant,
            username,
            password,
            authurl,
            context,
        ) = self.make_parameters()
        nova_power_driver = NovaPowerDriver()
        power_control_nova_mock = self.patch(
            nova_power_driver, "power_control_nova"
        )
        power_control_nova_mock.return_value = "off"
        expected_result = nova_power_driver.power_query(system_id, context)

        power_control_nova_mock.assert_called_once_with("query", **context)
        self.assertEqual(expected_result, "off")
