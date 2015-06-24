# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Virsh Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.hardware.virsh import (
    power_control_virsh,
    power_state_virsh,
)
from provisioningserver.drivers.power import PowerDriver


def extract_virsh_parameters(params):
    poweraddr = params.get('power_address')
    machine = params.get('power_id')
    password = params.get('power_pass')
    return poweraddr, machine, password


class VirshPowerDriver(PowerDriver):

    name = 'virsh'
    description = "Virsh Power Driver."
    settings = []

    def power_on(self, system_id, **kwargs):
        """Power on Virsh node."""
        power_change = 'on'
        poweraddr, machine, password = extract_virsh_parameters(kwargs)
        power_control_virsh(
            poweraddr, machine, power_change, password)

    def power_off(self, system_id, **kwargs):
        """Power off Virsh node."""
        power_change = 'off'
        poweraddr, machine, password = extract_virsh_parameters(kwargs)
        power_control_virsh(
            poweraddr, machine, power_change, password)

    def power_query(self, system_id, **kwargs):
        """Power query Virsh node."""
        poweraddr, machine, password = extract_virsh_parameters(kwargs)
        return power_state_virsh(poweraddr, machine, password)
