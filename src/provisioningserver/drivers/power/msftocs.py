# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Msftocs Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.hardware.msftocs import (
    power_control_msftocs,
    power_state_msftocs,
)
from provisioningserver.drivers.power import PowerDriver


def extract_msftocs_parameters(params):
    ip = params.get('power_address')
    port = params.get('power_port')
    username = params.get('power_user')
    password = params.get('power_pass')
    blade_id = params.get('blade_id')
    return ip, port, username, password, blade_id


class MicrosoftOCSPowerDriver(PowerDriver):

    name = 'msftocs'
    description = "MicrosoftOCS Power Driver."
    settings = []

    def detect_missing_packages(self):
        # uses urllib2 http client - nothing to look for!
        return []

    def power_on(self, system_id, **kwargs):
        """Power on MicrosoftOCS node."""
        power_change = 'on'
        ip, port, username, password, blade_id = (
            extract_msftocs_parameters(kwargs))
        power_control_msftocs(
            ip, port, username, password, power_change)

    def power_off(self, system_id, **kwargs):
        """Power off MicrosoftOCS node."""
        power_change = 'off'
        ip, port, username, password, blade_id = (
            extract_msftocs_parameters(kwargs))
        power_control_msftocs(
            ip, port, username, password, power_change)

    def power_query(self, system_id, **kwargs):
        """Power query MicrosoftOCS node."""
        ip, port, username, password, blade_id = (
            extract_msftocs_parameters(kwargs))
        return power_state_msftocs(ip, port, username, password, blade_id)
