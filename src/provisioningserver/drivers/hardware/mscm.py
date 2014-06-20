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

import re

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

    def discover_nodes(self):
        """Discover all available nodes.

        Example of stdout from running "show node list":

        'show node list\r\r\nSlot ID    Proc Manufacturer
        Architecture         Memory Power Health\r\n----
        ----- ---------------------- --------------------
        ------ ----- ------\r\n 01  c1n1  Intel Corporation
        x86 Architecture     32 GB  On    OK \r\n 02  c2n1
        N/A                    No Asset Information \r\n\r\n'

        The regex 'c\d+n\d' is finding the node_id's c1-45n1-8
        """
        node_list = self._run_cli_command("show node list")
        return re.findall(r'c\d+n\d', node_list)

    def get_node_macaddr(self, node):
        """Get node MAC address(es).

        Example of stdout from running "show node macaddr <xnode_id>":

        'show node macaddr c1n1\r\r\nSlot ID    NIC 1 (Switch A)
        NIC 2 (Switch B)  NIC 3 (Switch A)  NIC 4 (Switch B)\r\n
        ---- ----- ----------------- ----------------- -----------------
        -----------------\r\n  1  c1n1  a0:1d:48:b5:04:34 a0:1d:48:b5:04:35
        a0:1d:48:b5:04:36 a0:1d:48:b5:04:37\r\n\r\n\r\n'

        The regex '[\:]'.join(['[0-9A-F]{1,2}'] * 6) is finding
        the MAC Addresses for the given node_id.
        """
        macs = self._run_cli_command("show node macaddr %s" % node)
        return re.findall(r':'.join(['[0-9a-f]{2}'] * 6), macs)

    def power_node_on(self, node):
        """Power node on."""
        return self._run_cli_command("set node power on %s" % node)

    def power_node_off(self, node):
        """Power node off."""
        return self._run_cli_command("set node power off %s" % node)

    def configure_node_boot_pxe(self, node):
        """Configure PXE boot for node."""
        return self._run_cli_command("set node boot pxe %s" % node)

    def configure_node_bootonce_pxe(self, node):
        """Configure PXE boot for node once."""
        return self._run_cli_command("set node bootonce pxe %s" % node)

    def get_node_arch(self, node):
        """Get node architecture."""
        node_detail = self._run_cli_command("show node detail %s" % node)
        return node_detail.split('CPU: ')[1].splitlines()[0]
