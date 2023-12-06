# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# Gnu Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.vmware`."""


from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.hardware.vmware import try_pyvmomi_import
from provisioningserver.drivers.power import vmware as vmware_module
from provisioningserver.drivers.power.vmware import (
    extract_vmware_parameters,
    VMwarePowerDriver,
)


class TestVMwarePowerDriver(MAASTestCase):
    def test_missing_packages(self):
        mock = self.patch(try_pyvmomi_import)
        mock.return_value = False
        driver = vmware_module.VMwarePowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["python3-pyvmomi"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(try_pyvmomi_import)
        mock.return_value = True
        driver = vmware_module.VMwarePowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def make_parameters(self, has_optional=True):
        system_id = factory.make_name("system_id")
        host = factory.make_name("power_address")
        username = factory.make_name("power_user")
        password = factory.make_name("power_pass")
        vm_name = factory.make_name("power_vm_name")
        uuid = factory.make_name("power_uuid")
        port = protocol = None
        context = {
            "system_id": system_id,
            "power_address": host,
            "power_user": username,
            "power_pass": password,
            "power_vm_name": vm_name,
            "power_uuid": uuid,
            "power_port": port,
            "power_protocol": protocol,
        }
        if not has_optional:
            context["power_port"] = ""
            context["power_protocol"] = ""
        return (
            system_id,
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
            context,
        )

    def test_extract_vmware_parameters_extracts_parameters(self):
        (
            system_id,
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
            context,
        ) = self.make_parameters()

        self.assertEqual(
            (host, username, password, vm_name, uuid, None, None),
            extract_vmware_parameters(context),
        )

    def test_extract_vmware_parameters_treats_optional_params_as_none(self):
        (
            system_id,
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
            context,
        ) = self.make_parameters(has_optional=False)

        self.assertEqual(
            (host, username, password, vm_name, uuid, port, protocol),
            extract_vmware_parameters(context),
        )

    def test_power_on_calls_power_control_vmware(self):
        power_change = "on"
        (
            system_id,
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
            context,
        ) = self.make_parameters()
        vmware_power_driver = VMwarePowerDriver()
        power_control_vmware = self.patch(
            vmware_module, "power_control_vmware"
        )
        vmware_power_driver.power_on(system_id, context)

        power_control_vmware.assert_called_once_with(
            host,
            username,
            password,
            vm_name,
            uuid,
            power_change,
            port,
            protocol,
        )

    def test_power_off_calls_power_control_vmware(self):
        power_change = "off"
        (
            system_id,
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
            context,
        ) = self.make_parameters()
        vmware_power_driver = VMwarePowerDriver()
        power_control_vmware = self.patch(
            vmware_module, "power_control_vmware"
        )
        vmware_power_driver.power_off(system_id, context)

        power_control_vmware.assert_called_once_with(
            host,
            username,
            password,
            vm_name,
            uuid,
            power_change,
            port,
            protocol,
        )

    def test_power_query_calls_power_query_vmware(self):
        (
            system_id,
            host,
            username,
            password,
            vm_name,
            uuid,
            port,
            protocol,
            context,
        ) = self.make_parameters()
        vmware_power_driver = VMwarePowerDriver()
        power_query_vmware = self.patch(vmware_module, "power_query_vmware")
        power_query_vmware.return_value = "off"
        expected_result = vmware_power_driver.power_query(system_id, context)

        power_query_vmware.assert_called_once_with(
            host, username, password, vm_name, uuid, port, protocol
        )
        self.assertEqual(expected_result, "off")
