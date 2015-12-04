# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Msftocs Power Driver."""

__all__ = []

from provisioningserver.drivers.hardware.msftocs import (
    power_control_msftocs,
    power_state_msftocs,
)
from provisioningserver.drivers.power import PowerDriver


def extract_msftocs_parameters(context):
    ip = context.get('power_address')
    port = context.get('power_port')
    username = context.get('power_user')
    password = context.get('power_pass')
    blade_id = context.get('blade_id')
    return ip, port, username, password, blade_id


class MicrosoftOCSPowerDriver(PowerDriver):

    name = 'msftocs'
    description = "MicrosoftOCS Power Driver."
    settings = []

    def detect_missing_packages(self):
        # uses urllib2 http client - nothing to look for!
        return []

    def power_on(self, system_id, context):
        """Power on MicrosoftOCS node."""
        power_change = 'on'
        ip, port, username, password, blade_id = (
            extract_msftocs_parameters(context))
        power_control_msftocs(
            ip, port, username, password, power_change)

    def power_off(self, system_id, context):
        """Power off MicrosoftOCS node."""
        power_change = 'off'
        ip, port, username, password, blade_id = (
            extract_msftocs_parameters(context))
        power_control_msftocs(
            ip, port, username, password, power_change)

    def power_query(self, system_id, context):
        """Power query MicrosoftOCS node."""
        ip, port, username, password, blade_id = (
            extract_msftocs_parameters(context))
        return power_state_msftocs(ip, port, username, password, blade_id)
