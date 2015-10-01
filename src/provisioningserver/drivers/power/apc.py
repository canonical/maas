# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""American Power Conversion (APC) Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.hardware.apc import (
    power_control_apc,
    power_state_apc,
    required_package,
)
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.utils import shell


def extract_apc_parameters(params):
    ip = params.get('power_address')
    outlet = params.get('node_outlet')
    power_on_delay = params.get('power_on_delay')
    return ip, outlet, power_on_delay


class APCPowerDriver(PowerDriver):

    name = 'apc'
    description = "APC Power Driver."
    settings = []

    def detect_missing_packages(self):
        binary, package = required_package()
        if not shell.has_command_available(binary):
            return [package]
        return []

    def power_on(self, system_id, **kwargs):
        """Power on Apc outlet."""
        power_change = 'on'
        ip, outlet, power_on_delay = extract_apc_parameters(kwargs)
        power_control_apc(
            ip, outlet, power_change, power_on_delay)

    def power_off(self, system_id, **kwargs):
        """Power off APC outlet."""
        power_change = 'off'
        ip, outlet, power_on_delay = extract_apc_parameters(kwargs)
        power_control_apc(
            ip, outlet, power_change, power_on_delay)

    def power_query(self, system_id, **kwargs):
        """Power query APC outlet."""
        ip, outlet, _ = extract_apc_parameters(kwargs)
        return power_state_apc(ip, outlet)
