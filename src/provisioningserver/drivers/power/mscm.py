# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Moonshot HP iLO Chassis Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.hardware.mscm import (
    power_control_mscm,
    power_state_mscm,
)
from provisioningserver.drivers.power import PowerDriver


def extract_mscm_parameters(params):
    host = params.get('power_address')
    username = params.get('power_user')
    password = params.get('power_pass')
    node_id = params.get('node_id')
    return host, username, password, node_id


class MSCMPowerDriver(PowerDriver):

    name = 'mscm'
    description = "Moonshot HP iLO Chassis Manager Power Driver."
    settings = []

    def detect_missing_packages(self):
        # uses pure-python paramiko ssh client - nothing to look for!
        return []

    def power_on(self, system_id, **kwargs):
        """Power on MSCM node."""
        host, username, password, node_id = extract_mscm_parameters(kwargs)
        power_control_mscm(
            host, username, password, node_id, power_change='on')

    def power_off(self, system_id, **kwargs):
        """Power off MSCM node."""
        host, username, password, node_id = extract_mscm_parameters(kwargs)
        power_control_mscm(
            host, username, password, node_id, power_change='off')

    def power_query(self, system_id, **kwargs):
        """Power query MSCM node."""
        host, username, password, node_id = extract_mscm_parameters(kwargs)
        return power_state_mscm(host, username, password, node_id)
