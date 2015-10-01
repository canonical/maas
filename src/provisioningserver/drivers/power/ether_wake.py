# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Template-based ether-wake Power Driver."""

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.utils import shell


class EtherWakePowerDriver(PowerDriver):
    name = 'ether_wake'
    description = "Ether-wake Power Driver."
    settings = []

    def detect_missing_packages(self):
        if shell.has_command_available('wakeonlan') or \
                shell.has_command_available('etherwake'):
            return []
        # you need one or the other, not both
        return ['wakeonlan or etherwake']

    def power_on(self, system_id, **kwargs):
        raise NotImplementedError

    def power_off(self, system_id, **kwargs):
        raise NotImplementedError

    def power_query(self, system_id, **kwargs):
        raise NotImplementedError
