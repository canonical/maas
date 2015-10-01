# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Template-based DLI Power Driver."""

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.utils import shell


class DLIPowerDriver(PowerDriver):
    name = 'dli'
    description = "DLI Power Driver."
    settings = []

    def detect_missing_packages(self):
        if not shell.has_command_available('wget'):
            return ['wget']
        return []

    def power_on(self, system_id, **kwargs):
        raise NotImplementedError

    def power_off(self, system_id, **kwargs):
        raise NotImplementedError

    def power_query(self, system_id, **kwargs):
        raise NotImplementedError
