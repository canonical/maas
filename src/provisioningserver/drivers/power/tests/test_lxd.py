# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.lxd`."""

__all__ = []

from os.path import join
from unittest.mock import Mock

from testtools.matchers import Equals

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import lxd as lxd_module
from provisioningserver.maas_certificates import (
    MAAS_CERTIFICATE,
    MAAS_PRIVATE_KEY,
)


class TestLXDPowerDriver(MAASTestCase):
    def test_no_missing_packages(self):
        driver = lxd_module.LXDPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters_context(self):
        return {
            "power_address": "".join(
                [
                    factory.make_name("power_address"),
                    ":%s" % factory.pick_port(),
                ]
            ),
            "instance_name": factory.make_name("instance_name"),
            "password": factory.make_name("password"),
        }

    def make_parameters(self, context):
        return (
            context.get("power_address"),
            context.get("instance_name"),
            context.get("password"),
        )

    def test_get_url(self):
        driver = lxd_module.LXDPowerDriver()
        context = {"power_address": factory.make_hostname()}

        # Test ip adds protocol and port
        self.assertEqual(
            join("https://", "%s:%d" % (context["power_address"], 8443)),
            driver.get_url(context),
        )

        # Test ip:port adds protocol
        context["power_address"] += ":1234"
        self.assertEqual(
            join("https://", "%s" % context["power_address"]),
            driver.get_url(context),
        )

        # Test protocol:ip adds port
        context["power_address"] = join("https://", factory.make_hostname())
        self.assertEqual(
            "%s:%d" % (context.get("power_address"), 8443),
            driver.get_url(context),
        )

        # Test protocol:ip:port doesn't do anything
        context["power_address"] += ":1234"
        self.assertEqual(context.get("power_address"), driver.get_url(context))

    def test__get_client(self):
        context = self.make_parameters_context()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extensions.return_value = True
        client.trusted = False
        driver = lxd_module.LXDPowerDriver()
        endpoint = driver.get_url(context)
        returned_client = driver.get_client(
            factory.make_name("system_id"), context
        )
        self.assertThat(
            Client,
            MockCalledOnceWith(
                endpoint=endpoint,
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
                verify=False,
            ),
        )
        self.assertThat(
            client.authenticate, MockCalledOnceWith(context["password"])
        )
        self.assertEquals(client, returned_client)

    def test_get_client_raises_error_when_lxd_does_not_support_vms(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extensions.return_value = False
        driver = lxd_module.LXDPowerDriver()
        error = self.assertRaises(
            lxd_module.LXDError, driver.get_machine, system_id, context
        )
        self.assertEqual(
            "Please upgrade your LXD host to 3.19+ for virtual machine support.",
            str(error),
        )
        self.assertThat(
            client.has_api_extensions, MockCalledOnceWith("virtual-machines")
        )

    def test_get_client_raises_error_when_not_trusted_and_no_password(self):
        context = self.make_parameters_context()
        context["password"] = None
        system_id = factory.make_name("system_id")
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extensions.return_value = True
        client.trusted = False
        driver = lxd_module.LXDPowerDriver()
        error = self.assertRaises(
            lxd_module.LXDError, driver.get_machine, system_id, context
        )
        self.assertEqual(
            f"{system_id}: Certificate is not trusted and no password was given.",
            str(error),
        )
        self.assertThat(
            client.has_api_extensions, MockCalledOnceWith("virtual-machines")
        )

    def test_get_client_raises_error_when_cannot_connect(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        Client = self.patch(lxd_module, "Client")
        Client.side_effect = lxd_module.ClientConnectionFailed()
        driver = lxd_module.LXDPowerDriver()
        error = self.assertRaises(
            lxd_module.LXDError, driver.get_machine, system_id, context
        )
        self.assertEqual(
            f"{system_id}: Failed to connect to the LXD REST API.", str(error)
        )

    def test__get_machine(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        driver = lxd_module.LXDPowerDriver()
        Client = self.patch(driver, "get_client")
        client = Client.return_value
        mock_machine = Mock()
        client.virtual_machines.get.return_value = mock_machine
        returned_machine = driver.get_machine(system_id, context)
        self.assertThat(Client, MockCalledOnceWith(system_id, context))
        self.assertEquals(mock_machine, returned_machine)

    def test_get_machine_raises_error_when_machine_not_found(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        instance_name = context.get("instance_name")
        driver = lxd_module.LXDPowerDriver()
        Client = self.patch(driver, "get_client")
        client = Client.return_value
        client.virtual_machines.get.side_effect = lxd_module.NotFound("Error")

        error = self.assertRaises(
            lxd_module.LXDError, driver.get_machine, system_id, context
        )
        self.assertEqual(
            f"{system_id}: LXD VM {instance_name} not found.", str(error)
        )

    def test__power_on(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        driver = lxd_module.LXDPowerDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 110
        driver.power_on(system_id, context)
        self.assertThat(mock_machine.start, MockCalledOnceWith())

    def test__power_off(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        driver = lxd_module.LXDPowerDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 103
        driver.power_off(system_id, context)
        self.assertThat(mock_machine.stop, MockCalledOnceWith())

    def test__power_query(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        driver = lxd_module.LXDPowerDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 103
        state = driver.power_query(system_id, context)
        self.assertThat(state, Equals("on"))

    def test__power_query_raises_error_on_unknown_state(self):
        context = self.make_parameters_context()
        system_id = factory.make_name("system_id")
        driver = lxd_module.LXDPowerDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 106
        error = self.assertRaises(
            lxd_module.LXDError, driver.power_query, system_id, context
        )
        self.assertEqual(
            f"{system_id}: Unknown power status code: {mock_machine.status_code}",
            str(error),
        )
