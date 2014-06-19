# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for managing nodes via the Moonshot HP iLO Chassis Manager CLI.

This module provides support for interacting with HP Moonshot iLO Chassis
Management (MSCM) CLI via SSH, and for using that support to allow MAAS to
manage systems via iLO.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )
str = None

__metaclass__ = type
__all__ = []

from paramiko import (
    AutoAddPolicy,
    SSHClient,
    )


class MSCM_CLI_API:
    """An API for interacting with the Moonshot iLO CM CLI."""

    def __init__(self, host, username, password):
        """MSCM_CLI_API Constructor."""
        self.host = host
        self.username = username
        self.password = password
        self._ssh = SSHClient()
        self._ssh.set_missing_host_key_policy(AutoAddPolicy())

    def _run_cli_command(self, command):
        """Run a single command and return unparsed text from stdout."""
        self._ssh.connect(
            self.host, username=self.username, password=self.password)
        try:
            _, stdout, _ = self._ssh.exec_command(command)
            output = stdout.read()
        finally:
            self._ssh.close()

        return output
