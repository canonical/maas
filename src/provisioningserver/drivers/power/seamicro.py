# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SeaMicro Power Driver."""

__all__ = []

from provisioningserver.drivers.hardware.seamicro import (
    power_control_seamicro15k_v09,
    power_control_seamicro15k_v2,
    power_query_seamicro15k_v2,
)
from provisioningserver.drivers.power import (
    PowerDriver,
    PowerFatalError,
)
from provisioningserver.utils import shell
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)


def extract_seamicro_parameters(context):
    ip = context.get('power_address')
    username = context.get('power_user')
    password = context.get('power_pass')
    server_id = context.get('system_id')
    power_control = context.get('power_control')
    return ip, username, password, server_id, power_control


class SeaMicroPowerDriver(PowerDriver):

    name = 'sm15k'
    description = "SeaMicro Power Driver."
    settings = []

    def detect_missing_packages(self):
        if not shell.has_command_available('ipmitool'):
            return ['ipmitool']
        return []

    def _power_control_seamicro15k_ipmi(
            self, ip, username, password, server_id, power_change):
        """Power on/off SeaMicro node via ipmitool."""
        power_mode = 1 if power_change == 'on' else 6
        try:
            call_and_check([
                'ipmitool', '-I', 'lanplus', '-H', ip, '-U', username,
                '-P', password, 'raw', '0x2E', '1', '0x00', '0x7d',
                '0xab', power_mode, '0', server_id,
                ])
        except ExternalProcessError as e:
            raise PowerFatalError(
                "Failed to power %s %s at %s: %s" % (
                    power_change, server_id, ip, e.output_as_unicode))

    def _power(self, power_change, context):
        """Power SeaMicro node."""
        ip, username, password, server_id, power_control = (
            extract_seamicro_parameters(context))
        if power_control == 'ipmi':
            self._power_control_seamicro15k_ipmi(
                ip, username, password, server_id, power_change=power_change)
        elif power_control == 'restapi':
            power_control_seamicro15k_v09(
                ip, username, password, server_id, power_change=power_change)
        elif power_control == 'restapi2':
            power_control_seamicro15k_v2(
                ip, username, password, server_id, power_change=power_change)

    def power_on(self, system_id, context):
        """Power on SeaMicro node."""
        self._power('on', context)

    def power_off(self, system_id, context):
        """Power off SeaMicro node."""
        self._power('off', context)

    def power_query(self, system_id, context):
        """Power query SeaMicro node."""
        # Query the state.
        # Only supported by REST v2.
        ip, username, password, _, power_control = (
            extract_seamicro_parameters(context))
        if power_control == 'restapi2':
            return power_query_seamicro15k_v2(
                ip, username, password, system_id)
        else:
            return 'unknown'
