# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Moonshot IPMI Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import os
import re

from provisioningserver.drivers.power import (
    PowerActionError,
    PowerDriver,
)
from provisioningserver.utils import shell
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)


class MoonshotIPMIPowerDriver(PowerDriver):

    name = 'moonshot'
    description = "Moonshot IPMI Power Driver."
    settings = []

    def detect_missing_packages(self):
        if not shell.has_command_available('ipmitool'):
            return ['ipmitool']
        return []

    def _issue_ipmitool_command(
            self, power_change, ipmitool=None, power_address=None,
            power_user=None, power_pass=None, power_hwaddress=None, **extra):
        """Issue ipmitool command for HP Moonshot cartridge."""
        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        command = (
            ipmitool, '-I', 'lanplus', '-H', power_address,
            '-U', power_user, '-P', power_pass
        ) + tuple(power_hwaddress.split())
        if power_change == 'pxe':
            command += ('chassis', 'bootdev', 'pxe')
        else:
            command += ('power', power_change)
        try:
            stdout = call_and_check(command, env=env)
            stdout = stdout.decode('utf-8')
        except ExternalProcessError as e:
            raise PowerActionError(
                "Failed to execute %s for cartridge %s at %s: %s" % (
                    command, power_hwaddress,
                    power_address, e.output_as_unicode))
        else:
            # Return output if power query
            if power_change == 'status':
                match = re.search(r'\b(on|off)\b$', stdout)
                return stdout if match is None else match.group(0)

    def power_on(self, system_id, context):
        self._issue_ipmitool_command('pxe', **context)
        self._issue_ipmitool_command('on', **context)

    def power_off(self, system_id, context):
        self._issue_ipmitool_command('off', **context)

    def power_query(self, system_id, context):
        return self._issue_ipmitool_command('status', **context)
