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
__all__ = [
    'power_control_mscm',
    'power_state_mscm',
    'probe_and_enlist_mscm',
]

import re

from paramiko import (
    AutoAddPolicy,
    SSHClient,
    )
import provisioningserver.utils as utils


cartridge_mapping = {
    'ProLiant Moonshot Cartridge': 'amd64/generic',
    'ProLiant m300 Server Cartridge': 'amd64/generic',
    'ProLiant m350 Server Cartridge': 'amd64/generic',
    'ProLiant m400 Server Cartridge': 'arm64/xgene-uboot',
    'ProLiant m500 Server Cartridge': 'amd64/generic',
    'ProLiant m700 Server Cartridge': 'amd64/generic',
    'ProLiant m710 Server Cartridge': 'amd64/generic',
    'ProLiant m800 Server Cartridge': 'armhf/keystone',
    'Default': 'amd64/generic',
}


class MSCMState:
    OFF = "Off"
    ON = "On"


class MSCMError(Exception):
    """Failure communicating to MSCM. """


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

    def get_node_macaddr(self, node_id):
        """Get node MAC address(es).

        Example of stdout from running "show node macaddr <node_id>":

        'show node macaddr c1n1\r\r\nSlot ID    NIC 1 (Switch A)
        NIC 2 (Switch B)  NIC 3 (Switch A)  NIC 4 (Switch B)\r\n
        ---- ----- ----------------- ----------------- -----------------
        -----------------\r\n  1  c1n1  a0:1d:48:b5:04:34 a0:1d:48:b5:04:35
        a0:1d:48:b5:04:36 a0:1d:48:b5:04:37\r\n\r\n\r\n'

        The regex '[\:]'.join(['[0-9A-F]{1,2}'] * 6) is finding
        the MAC Addresses for the given node_id.
        """
        macs = self._run_cli_command("show node macaddr %s" % node_id)
        return re.findall(r':'.join(['[0-9a-f]{2}'] * 6), macs)

    def get_node_arch(self, node_id):
        """Get node architecture.

        Example of stdout from running "show node info <node_id>":

        'show node info c1n1\r\r\n\r\nCartridge #1 \r\n  Type: Compute\r\n
        Manufacturer: HP\r\n  Product Name: ProLiant m500 Server Cartridge\r\n'

        Parsing this retrieves 'ProLiant m500 Server Cartridge'
        """
        node_detail = self._run_cli_command("show node info %s" % node_id)
        cartridge = node_detail.split('Product Name: ')[1].splitlines()[0]
        if cartridge in cartridge_mapping:
            return cartridge_mapping[cartridge]
        else:
            return cartridge_mapping['Default']

    def get_node_power_state(self, node_id):
        """Get power state of node (on/off).

        Example of stdout from running "show node power <node_id>":

        'show node power c1n1\r\r\n\r\nCartridge #1\r\n  Node #1\r\n
        Power State: On\r\n'

        Parsing this retrieves 'On'
        """
        power_state = self._run_cli_command("show node power %s" % node_id)
        return power_state.split('Power State: ')[1].splitlines()[0]

    def power_node_on(self, node_id):
        """Power node on."""
        return self._run_cli_command("set node power on %s" % node_id)

    def power_node_off(self, node_id):
        """Power node off."""
        return self._run_cli_command("set node power off force %s" % node_id)

    def configure_node_boot_m2(self, node_id):
        """Configure HDD boot for node."""
        return self._run_cli_command("set node boot M.2 %s" % node_id)

    def configure_node_bootonce_pxe(self, node_id):
        """Configure PXE boot for node once."""
        return self._run_cli_command("set node bootonce pxe %s" % node_id)


def power_control_mscm(host, username, password, node_id, power_change):
    """Handle calls from the power template for nodes with a power type
    of 'mscm'.
    """
    mscm = MSCM_CLI_API(host, username, password)

    if power_change == 'off':
        mscm.power_node_off(node_id)
    elif power_change == 'on':
        if mscm.get_node_power_state(node_id) == MSCMState.ON:
            mscm.power_node_off(node_id)
        mscm.configure_node_bootonce_pxe(node_id)
        mscm.power_node_on(node_id)
    else:
        raise MSCMError("Unexpected maas power mode.")


def power_state_mscm(host, username, password, node_id):
    """Return the power state for the mscm machine."""
    mscm = MSCM_CLI_API(host, username, password)
    try:
        power_state = mscm.get_node_power_state(node_id)
    except:
        raise MSCMError("Failed to retrieve power state.")

    if power_state == MSCMState.OFF:
        return 'off'
    elif power_state == MSCMState.ON:
        return 'on'
    raise MSCMError('Unknown power state: %s' % power_state)


def probe_and_enlist_mscm(host, username, password):
    """ Extracts all of nodes from mscm, sets all of them to boot via M.2 by,
    default, sets them to bootonce via PXE, and then enlists them into MAAS.
    """
    mscm = MSCM_CLI_API(host, username, password)
    try:
        # if discover_nodes works, we have access to the system
        nodes = mscm.discover_nodes()
    except:
        raise MSCMError(
            "Failed to probe nodes for mscm with host=%s, "
            "username=%s, password=%s"
            % (host, username, password))

    for node_id in nodes:
        # Set default boot to M.2
        mscm.configure_node_boot_m2(node_id)
        params = {
            'power_address': host,
            'power_user': username,
            'power_pass': password,
            'node_id': node_id,
        }
        arch = mscm.get_node_arch(node_id)
        macs = mscm.get_node_macaddr(node_id)
        utils.create_node(macs, arch, 'mscm', params)
