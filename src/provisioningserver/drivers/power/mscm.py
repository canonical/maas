# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
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
    MSCMError,
    power_control_mscm,
    power_state_mscm,
)
from provisioningserver.drivers.power import (
    PowerDriver,
    PowerError,
)


def extract_mscm_parameters(context):
    host = context.get('power_address')
    username = context.get('power_user')
    password = context.get('power_pass')
    node_id = context.get('node_id')
    return host, username, password, node_id


class MSCMPowerDriver(PowerDriver):

    name = 'mscm'
    description = "Moonshot HP iLO Chassis Manager Power Driver."
    settings = []

    def detect_missing_packages(self):
        # uses pure-python paramiko ssh client - nothing to look for!
        return []

    def power_on(self, system_id, context):
        """Power on MSCM node."""
        host, username, password, node_id = extract_mscm_parameters(context)
        try:
            power_control_mscm(
                host, username, password, node_id, power_change='on')
        except MSCMError as e:
            raise PowerError(
                "MSCM Power Driver could not power on node %s: %s"
                % (node_id, e))

    def power_off(self, system_id, context):
        """Power off MSCM node."""
        host, username, password, node_id = extract_mscm_parameters(context)
        try:
            power_control_mscm(
                host, username, password, node_id, power_change='off')
        except MSCMError as e:
            raise PowerError(
                "MSCM Power Driver could not power off node %s: %s"
                % (node_id, e))

    def power_query(self, system_id, context):
        """Power query MSCM node."""
        host, username, password, node_id = extract_mscm_parameters(context)
        try:
            return power_state_mscm(host, username, password, node_id)
        except MSCMError as e:
            raise PowerError(
                "MSCM Power Driver could not power query node %s: %s"
                % (node_id, e))
