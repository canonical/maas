# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.virsh`."""

__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import virsh as virsh_module
from provisioningserver.drivers.power.virsh import (
    extract_virsh_parameters,
    VirshPowerDriver,
)
from provisioningserver.utils.shell import has_command_available
from testtools.matchers import Equals


class TestVirshPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = virsh_module.VirshPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(["libvirt-clients"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = virsh_module.VirshPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters(self):
        system_id = factory.make_name("system_id")
        poweraddr = factory.make_name("power_address")
        machine = factory.make_name("power_id")
        password = factory.make_name("power_pass")
        context = {
            "system_id": system_id,
            "power_address": poweraddr,
            "power_id": machine,
            "power_pass": password,
        }
        return system_id, poweraddr, machine, password, context

    def test_extract_virsh_parameters_extracts_parameters(self):
        (
            system_id,
            poweraddr,
            machine,
            password,
            context,
        ) = self.make_parameters()

        self.assertItemsEqual(
            (poweraddr, machine, password), extract_virsh_parameters(context)
        )

    def test_power_on_calls_power_control_virsh(self):
        power_change = "on"
        (
            system_id,
            poweraddr,
            machine,
            password,
            context,
        ) = self.make_parameters()
        virsh_power_driver = VirshPowerDriver()
        power_control_virsh = self.patch(virsh_module, "power_control_virsh")
        virsh_power_driver.power_on(system_id, context)

        self.assertThat(
            power_control_virsh,
            MockCalledOnceWith(poweraddr, machine, power_change, password),
        )

    def test_power_off_calls_power_control_virsh(self):
        power_change = "off"
        (
            system_id,
            poweraddr,
            machine,
            password,
            context,
        ) = self.make_parameters()
        virsh_power_driver = VirshPowerDriver()
        power_control_virsh = self.patch(virsh_module, "power_control_virsh")
        virsh_power_driver.power_off(system_id, context)

        self.assertThat(
            power_control_virsh,
            MockCalledOnceWith(poweraddr, machine, power_change, password),
        )

    def test_power_query_calls_power_state_virsh(self):
        (
            system_id,
            poweraddr,
            machine,
            password,
            context,
        ) = self.make_parameters()
        virsh_power_driver = VirshPowerDriver()
        power_state_virsh = self.patch(virsh_module, "power_state_virsh")
        power_state_virsh.return_value = "off"
        expected_result = virsh_power_driver.power_query(system_id, context)

        self.expectThat(
            power_state_virsh, MockCalledOnceWith(poweraddr, machine, password)
        )
        self.expectThat(expected_result, Equals("off"))
