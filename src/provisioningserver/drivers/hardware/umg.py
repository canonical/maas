# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for managing nodes via a Emerson Network Power Universal
Management Gatway (UMG).

The UMG is an appliance for managing servers and other devices remotely.
It can interact with managed systems via IPMI and other network
protocols, providing services like remote console, power control, and
sensor aggregration.

This module provides support for interacting UMG's SSH based CLI, and
for using that support to allow MAAS to manage systems via UMG.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )
str = None

__metaclass__ = type
__all__ = []

from collections import namedtuple
import re

import paramiko


ShowOutput = namedtuple('ShowOutput', ('directories', 'settings'))

directories_pattern = r'''
    ^\|__       # Start of line followed by '|__'
    (.*)        # Capture remaining text on line
    \r$         # End of line with carriage return.
'''
directories_re = re.compile(directories_pattern, re.MULTILINE | re.VERBOSE)

settings_pattern = r'''
    ^\s\*\s     # Start of line followed by ' * '
    (\w+)=(.*)  # Capture key and value
    \r$         # End of line with carriage return.
'''
settings_re = re.compile(settings_pattern, re.MULTILINE | re.VERBOSE)


class UMG_CLI_API:
    """An API for interacting with the UMG CLI.

    This API exposes actions that are useful to MAAS, but not
    necessarily general purpose.

    Some terms:
    command - input for the CLI.  The CLI will run a command and return
    some output.
    SP - Service Processor. A service processor sometimes, but
    not always, manages a server. There are also service processors for
    other things (CMM).
    target - things managed by the UMG. For MAAS's use, these are
    servers.
    """

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def _run_cli_command(self, command):
        """Run a single command and return unparsed text from stdout.

        This method opens and closes an SSH connection each time it's
        called - the CLI doesn't appear to support multiple commands per
        connection.
        """
        full_command = 'cli -s %s' % (command)
        self._ssh.connect(
            self.host, username=self.username, password=self.password)
        try:
            _, stdout, _ = self._ssh.exec_command(full_command)
            output = stdout.read()
        finally:
            self._ssh.close()

        return output

    def _parse_show_output(self, text):
        """Parse the output of a 'show' command.

        The show command shows information about a directory. The
        directory may contain other directories, and may have settings.

        This method returns a list of the directories and a dictionary
        containing the settings, encapsulated in a ShowOutput object.

        Each line of output is follwed by '\r\n'.

        Example output - all directories:
          Cli>show /targets/SP
          |__1F-C9-DF_CMM-1-1
          |__1F-C9-DF_CMM-1-2
          |__1F-C9-DF_MMC-1-1-28
          |__1F-C9-DF_MMC-1-1-31
          |__1F-C9-DF_MMC-1-2-28
          |__1F-C9-DF_MMC-1-2-31

        Example output - directories and text:
          Cli>show /targets/SP/1F-C9-DF_CMM-1-1
           * alias=1F-C9-DF_CMM-1-1
           * internalId=181
           * ipAddress=10.216.160.113
          |__powerControl
        """

        directories = directories_re.findall(text)
        settings = dict(settings_re.findall(text))
        return ShowOutput(directories, settings)

    def _show_command(self, command):
        """Run a show command and return its parsed output."""
        output_text = self._run_cli_command(command)
        output = self._parse_show_output(output_text)
        return output

    def show_targets(self):
        """Return a list of targets from /targets/SP."""
        output = self._show_command('show /targets/SP')
        return output

    def show_target(self, target):
        """Show the details of a target from /target/SP.

        This provides informations about the SP - like IP
        address, type, and power status.
        """
        output = self._show_command('show /targets/SP/%s' % (target))
        return output

    def power_control_target(self, target, control):
        """Issue a power command to a target.

        Targets are SP names.  Valid controls are 'cycle', 'on', 'off'.
        """
        command = 'set targets/SP/%s/powerControl powerCtrlType=%s' % (
            target, control)
        self._run_cli_command(command)
