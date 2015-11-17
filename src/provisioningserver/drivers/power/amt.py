# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Template-based AMT Power Driver."""

str = None

__metaclass__ = type
__all__ = []

from provisioningserver.drivers.power import PowerDriver
from provisioningserver.utils import shell


REQUIRED_PACKAGES = [["amttool", "amtterm"], ["wsman", "wsmancli"]]


class AMTPowerDriver(PowerDriver):
    name = 'amt'
    description = "AMT Power Driver."
    settings = []

    def detect_missing_packages(self):
        missing_packages = []
        # when this becomes a non-templated, registered power driver, we can
        # detect what version of AMT is on the Node to find out if wsman is
        # required (see amt.template). For now, we assume wsman is required
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.append(package)
        return missing_packages

    def power_on(self, system_id, context):
        raise NotImplementedError

    def power_off(self, system_id, context):
        raise NotImplementedError

    def power_query(self, system_id, context):
        raise NotImplementedError
