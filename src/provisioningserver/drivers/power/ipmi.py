# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""IPMI Power Driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from subprocess import (
    PIPE,
    Popen,
)
from tempfile import NamedTemporaryFile

from provisioningserver.drivers.power import (
    PowerAuthError,
    PowerDriver,
    PowerFatalError,
)
from provisioningserver.utils.network import find_ip_via_arp
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)


IPMI_CONFIG = """\
Section Chassis_Boot_Flags
        Boot_Flags_Persistent                         No
        Boot_Device                                   PXE
EndSection
"""


def is_set(setting):
    return not (setting is None or setting == "" or setting.isspace())


class IPMIPowerDriver(PowerDriver):

    name = 'ipmi'
    description = "IPMI Power Driver."
    settings = []

    @staticmethod
    def _issue_ipmi_chassis_config_command(command, change, address):
        with NamedTemporaryFile() as tmp_config:
            # Write out the chassis configuration.
            tmp_config.write(IPMI_CONFIG)
            tmp_config.flush()
            # Use it when running the chassis config command.
            # XXX: Not using call_and_check here because we
            # need to check stderr.
            command = tuple(command) + ("--filename", tmp_config.name)
            process = Popen(command, stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            stderr = stderr.strip()
        if "password invalid" in stderr:
            raise PowerAuthError("Invalid password.")
        if process.returncode != 0:
            raise PowerFatalError(
                "Failed to power %s %s: %s" % (change, address, stderr))

    @staticmethod
    def _issue_ipmi_power_command(command, change, address):
        command = tuple(command)  # For consistency when testing.
        try:
            output = call_and_check(command)
        except ExternalProcessError as e:
            raise PowerFatalError(
                "Failed to power %s %s: %s" % (
                    change, address, e.output_as_unicode))
        else:
            if 'on' in output:
                return 'on'
            elif 'off' in output:
                return 'off'
            else:
                return output

    def _issue_ipmi_command(
            self, power_change, power_address=None, power_user=None,
            power_pass=None, power_driver=None, power_off_mode=None,
            ipmipower=None, ipmi_chassis_config=None, mac_address=None,
            **extra):
        """Issue command to ipmipower, for the given system."""
        # This script deliberately does not check the current power state
        # before issuing the requested power command. See bug 1171418 for an
        # explanation.

        if is_set(mac_address) and not is_set(power_address):
            power_address = find_ip_via_arp(mac_address)

        # The `-W opensesspriv` workaround is required on many BMCs, and
        # should have no impact on BMCs that don't require it.
        # See https://bugs.launchpad.net/maas/+bug/1287964
        ipmi_chassis_config_command = [
            ipmi_chassis_config, '-W', 'opensesspriv']
        ipmipower_command = [
            ipmipower, '-W', 'opensesspriv']

        # Arguments in common between chassis config and power control. See
        # https://launchpad.net/bugs/1053391 for details of modifying the
        # command for power_driver and power_user.
        common_args = []
        if is_set(power_driver):
            common_args.extend(("--driver-type", power_driver))
        common_args.extend(('-h', power_address))
        if is_set(power_user):
            common_args.extend(("-u", power_user))
        common_args.extend(('-p', power_pass))

        # Update the chassis config and power commands.
        ipmi_chassis_config_command.extend(common_args)
        ipmi_chassis_config_command.append('--commit')
        ipmipower_command.extend(common_args)

        # Before changing state run the chassis config command.
        if power_change in ("on", "off"):
            self._issue_ipmi_chassis_config_command(
                ipmi_chassis_config_command, power_change, power_address)

        # Additional arguments for the power command.
        if power_change == 'on':
            ipmipower_command.append('--cycle')
            ipmipower_command.append('--on-if-off')
        elif power_change == 'off':
            if power_off_mode == 'soft':
                ipmipower_command.append('--soft')
            else:
                ipmipower_command.append('--off')
        elif power_change == 'query':
            ipmipower_command.append('--stat')

        # Update or query the power state.
        return self._issue_ipmi_power_command(
            ipmipower_command, power_change, power_address)

    def power_on(self, system_id, **kwargs):
        self._issue_ipmi_command('on', **kwargs)

    def power_off(self, system_id, **kwargs):
        self._issue_ipmi_command('off', **kwargs)

    def power_query(self, system_id, **kwargs):
        return self._issue_ipmi_command('query', **kwargs)
