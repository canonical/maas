# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for managing American Power Conversion (APC) PDU outlets via SNMP.

APC Network Management Card AOS and Rack PDU APP firmware versions supported:

v3.7.3
v3.7.4
"""

__all__ = [
    'power_control_apc',
    'power_state_apc',
]

from subprocess import (
    PIPE,
    Popen,
)
from time import sleep

from provisioningserver.utils.shell import ExternalProcessError


COMMON_ARGS = '-c private -v1 %s .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.%s'


class APCState(object):
    ON = '1'
    OFF = '2'


class APCException(Exception):
    """Failure communicating to the APC PDU. """


class APCSNMP:

    def run_process(self, command):
        proc = Popen(command.split(), stdout=PIPE)
        stdout, stderr = proc.communicate()

        if proc.returncode != 0:
            raise ExternalProcessError(
                proc.returncode, command.split(), stderr)
        return stdout.split(": ")[1].rstrip('\n')

    def power_off_outlet(self, ip, outlet):
        """Power off outlet."""
        command = 'snmpset ' + COMMON_ARGS % (ip, outlet) + ' i 2'
        return self.run_process(command)

    def power_on_outlet(self, ip, outlet, power_on_delay):
        """Power on outlet.

        This forces the outlet OFF first, then sleeps for `timeout` seconds,
        before turning it ON.
        """
        command = 'snmpset ' + COMMON_ARGS % (ip, outlet) + ' i 1'
        self.power_off_outlet(ip, outlet)
        sleep(power_on_delay)
        return self.run_process(command)

    def get_power_state_of_outlet(self, ip, outlet):
        """Get power state of outlet (ON/OFF)."""
        command = 'snmpget ' + COMMON_ARGS % (ip, outlet)
        return self.run_process(command)


def power_control_apc(ip, outlet, power_change, power_on_delay):
    """Handle calls from the power template for outlets with a power type
    of 'apc'.
    """
    apc = APCSNMP()

    if power_change == 'off':
        apc.power_off_outlet(ip, outlet)
    elif power_change == 'on':
        apc.power_on_outlet(ip, outlet, float(power_on_delay))
    else:
        raise AssertionError(
            "Unrecognised power change: %r" % (power_change,))


def power_state_apc(ip, outlet):
    """Return the power state for the APC PDU outlet."""
    apc = APCSNMP()

    power_state = apc.get_power_state_of_outlet(ip, outlet)
    if power_state == APCState.OFF:
        return 'off'
    elif power_state == APCState.ON:
        return 'on'
    raise APCException('Unknown power state: %r' % power_state)


def required_package():
    return ['snmpset', 'snmp']
