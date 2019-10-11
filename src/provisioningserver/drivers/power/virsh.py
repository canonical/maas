# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Virsh Power Driver."""

__all__ = []

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.hardware.virsh import (
    power_control_virsh,
    power_state_virsh,
)
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.utils import shell


REQUIRED_PACKAGES = [
    ["virsh", "libvirt-clients"],
    ["virt-login-shell", "libvirt-clients"],
]


def extract_virsh_parameters(context):
    poweraddr = context.get("power_address")
    machine = context.get("power_id")
    password = context.get("power_pass")
    return poweraddr, machine, password


class VirshPowerDriver(PowerDriver):

    name = "virsh"
    chassis = True
    description = "Virsh (virtual systems)"
    settings = [
        make_setting_field("power_address", "Power address", required=True),
        make_setting_field(
            "power_id", "Power ID", scope=SETTING_SCOPE.NODE, required=True
        ),
        make_setting_field(
            "power_pass",
            "Power password (optional)",
            required=False,
            field_type="password",
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    def detect_missing_packages(self):
        missing_packages = set()
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.add(package)
        return list(missing_packages)

    def power_on(self, system_id, context):
        """Power on Virsh node."""
        power_change = "on"
        poweraddr, machine, password = extract_virsh_parameters(context)
        power_control_virsh(poweraddr, machine, power_change, password)

    def power_off(self, system_id, context):
        """Power off Virsh node."""
        power_change = "off"
        poweraddr, machine, password = extract_virsh_parameters(context)
        power_control_virsh(poweraddr, machine, power_change, password)

    def power_query(self, system_id, context):
        """Power query Virsh node."""
        poweraddr, machine, password = extract_virsh_parameters(context)
        return power_state_virsh(poweraddr, machine, password)
