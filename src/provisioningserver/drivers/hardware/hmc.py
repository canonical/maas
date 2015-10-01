# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for managing lpars via the IBM Hardware Management Console (HMC).

This module provides support for interacting with IBM's HMC via SSH.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )
str = None

__metaclass__ = type
__all__ = [
    'power_control_hmc',
    'power_state_hmc',
]

from paramiko import (
    AutoAddPolicy,
    SSHClient,
    SSHException,
)


class HMCState:
    OFF = ('Shutting Down', 'Not Activated')
    ON = ('Starting', 'Running', 'Open Firmware')


class HMCException(Exception):
    """Failure communicating to HMC."""


class HMC:
    """An API for interacting with the HMC via SSH."""

    def __init__(self, ip, username, password):
        self.ip = ip
        self.username = username
        self.password = password
        self._ssh = SSHClient()
        self._ssh.set_missing_host_key_policy(AutoAddPolicy())

    def _run_cli_command(self, command):
        """Run a single command and return unparsed text from stdout."""
        self._ssh.connect(
            self.ip, username=self.username, password=self.password)
        try:
            _, stdout, _ = self._ssh.exec_command(command)
            output = stdout.read()
        finally:
            self._ssh.close()

        return output

    def get_lpar_power_state(self, server_name, lpar):
        """Get power state of lpar."""
        power_state = self._run_cli_command(
            "lssyscfg -m %s -r lpar -F name:state" % server_name)
        return power_state.split('%s:' % lpar)[1].split('\n')[0]

    def power_lpar_on(self, server_name, lpar):
        """Power lpar on.

        Set bootstring flag to boot via network by default.  This will set
        the default boot order to try and boot from the first five network
        interfaces it enumerates over.
        """
        return self._run_cli_command(
            "chsysstate -r lpar -m %s -o on -n %s --bootstring network-all" %
            (server_name, lpar))

    def power_lpar_off(self, server_name, lpar):
        """Power lpar off."""
        return self._run_cli_command(
            "chsysstate -r lpar -m %s -o shutdown -n %s --immed" %
            (server_name, lpar))


def power_control_hmc(ip, username, password, server_name, lpar, power_change):
    """Handle calls from the power template for nodes with a power type
    of 'hmc'.
    """
    hmc = HMC(ip, username, password)

    if power_change == 'off':
        hmc.power_lpar_off(server_name, lpar)
    elif power_change == 'on':
        if hmc.get_lpar_power_state(server_name, lpar) in HMCState.ON:
            hmc.power_lpar_off(server_name, lpar)
        hmc.power_lpar_on(server_name, lpar)
    else:
        raise HMCException("Unexpected maas power mode.")


def power_state_hmc(ip, username, password, server_name, lpar):
    """Return the power state for the hmc machine."""
    hmc = HMC(ip, username, password)
    try:
        power_state = hmc.get_lpar_power_state(server_name, lpar)
    except SSHException as e:
        raise HMCException("Failed to retrieve power state: %s" % e)

    if power_state in HMCState.OFF:
        return 'off'
    elif power_state in HMCState.ON:
        return 'on'
    raise HMCException('Unknown power state: %s' % power_state)


def required_package():
    return ['chsysstate', 'HMC Management Software']
