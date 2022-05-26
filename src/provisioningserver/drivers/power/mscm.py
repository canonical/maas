# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Moonshot HP iLO Chassis Power Driver.

Support for managing nodes via the Moonshot HP iLO Chassis Manager CLI.

This module provides support for interacting with HP Moonshot iLO Chassis
Management (MSCM) CLI via SSH, and for using that support to allow MAAS to
manage systems via iLO.
"""


import re
from socket import error as SOCKETError
from typing import Optional

from paramiko import AutoAddPolicy, SSHClient, SSHException

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerDriver,
    PowerFatalError,
)
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import synchronous

cartridge_mapping = {
    "ProLiant Moonshot Cartridge": "amd64/generic",
    "ProLiant m300 Server Cartridge": "amd64/generic",
    "ProLiant m350 Server Cartridge": "amd64/generic",
    "ProLiant m400 Server Cartridge": "arm64/xgene-uboot",
    "ProLiant m500 Server Cartridge": "amd64/generic",
    "ProLiant m700 Server Cartridge": "amd64/generic",
    "ProLiant m710 Server Cartridge": "amd64/generic",
    "ProLiant m720 Server Cartridge": "amd64/generic",
    "ProLiant m800 Server Cartridge": "armhf/keystone",
    "Default": "amd64/generic",
}


class MSCMState:
    OFF = ("Off", "Unavailable")
    ON = "On"


class MSCMPowerDriver(PowerDriver):

    name = "mscm"
    chassis = True
    can_probe = True
    can_set_boot_order = False
    description = "HP Moonshot - iLO Chassis Manager"
    settings = [
        make_setting_field(
            "power_address", "IP for MSCM CLI API", required=True
        ),
        make_setting_field("power_user", "MSCM CLI API user"),
        make_setting_field(
            "power_pass", "MSCM CLI API password", field_type="password"
        ),
        make_setting_field(
            "node_id",
            "Node ID - Must adhere to cXnY format "
            "(X=cartridge number, Y=node number).",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        # uses pure-python paramiko ssh client - nothing to look for!
        return []

    def run_mscm_command(
        self,
        command,
        power_address=None,
        power_user=None,
        power_pass=None,
        **extra
    ):
        """Run a single command on MSCM via SSH and return output."""
        try:
            ssh_client = SSHClient()
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            ssh_client.connect(
                power_address, username=power_user, password=power_pass
            )
            _, stdout, _ = ssh_client.exec_command(command)
            output = stdout.read().decode("utf-8")
        except (SSHException, EOFError, SOCKETError) as e:
            raise PowerConnError(
                "Could not make SSH connection to MSCM for "
                "%s on %s - %s" % (power_user, power_address, e)
            )
        finally:
            ssh_client.close()

        return output

    def power_on(self, system_id, context):
        """Power on MSCM node."""
        node_id = context["node_id"]
        # If node is on, power off first
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
        try:
            # Configure node to boot once from PXE
            self.run_mscm_command(
                "set node bootonce pxe %s" % node_id, **context
            )
            # Power node on
            self.run_mscm_command("set node power on %s" % node_id, **context)
        except PowerConnError as e:
            raise PowerActionError(
                "MSCM Power Driver unable to power on node %s: %s"
                % (context["node_id"], e)
            )

    def power_off(self, system_id, context):
        """Power off MSCM node."""
        try:
            # Power node off
            self.run_mscm_command(
                "set node power off force %s" % context["node_id"], **context
            )
        except PowerConnError as e:
            raise PowerActionError(
                "MSCM Power Driver unable to power off node %s: %s"
                % (context["node_id"], e)
            )

    def power_query(self, system_id, context):
        """Power query MSCM node."""
        try:
            # Retreive node power state
            #
            # Example of output from running "show node power <node_id>":
            # "show node power c1n1\r\r\n\r\nCartridge #1\r\n  Node #1\r\n
            # Power State: On\r\n"
            output = self.run_mscm_command(
                "show node power %s" % context["node_id"], **context
            )
        except PowerConnError as e:
            raise PowerActionError(
                "MSCM Power Driver unable to power query node %s: %s"
                % (context["node_id"], e)
            )
        match = re.search(r"Power State:\s*((O[\w]+|U[\w]+))", output)
        if match is None:
            raise PowerFatalError(
                "MSCM Power Driver unable to extract node power state from: %s"
                % output
            )
        else:
            power_state = match.group(1)
            if power_state in MSCMState.OFF:
                return "off"
            elif power_state == MSCMState.ON:
                return "on"


@synchronous
def probe_and_enlist_mscm(
    user: str,
    host: str,
    username: Optional[str],
    password: Optional[str],
    accept_all: bool = False,
    domain: str = None,
):
    """Extracts all of nodes from the MSCM, sets all of them to boot via M.2
    by, default, sets them to bootonce via PXE, and then enlists them into
    MAAS.  If accept_all is True, it will also commission them.
    """
    mscm_driver = MSCMPowerDriver()
    # Discover all available nodes
    #
    # Example of output from running "show node list":
    # "show node list\r\r\nSlot ID    Proc Manufacturer
    # Architecture         Memory Power Health\r\n----
    # ----- ---------------------- --------------------
    # ------ ----- ------\r\n 01  c1n1  Intel Corporation
    # x86 Architecture     32 GB  On    OK \r\n 02  c2n1
    # N/A                    No Asset Information \r\n\r\n'"
    node_list = mscm_driver.run_mscm_command(
        "show node list",
        power_address=host,
        power_user=username,
        power_pass=password,
    )
    nodes = re.findall(r"c\d+n\d", node_list)
    for node_id in nodes:
        params = {
            "power_address": host,
            "power_user": username,
            "power_pass": password,
            "node_id": node_id,
        }
        # Set default boot to M.2
        mscm_driver.run_mscm_command(
            "set node boot M.2 %s" % node_id, **params
        )
        # Retrieve node architecture
        #
        # Example of output from running "show node info <node_id>":
        # "show node info c1n1\r\r\n\r\nCartridge #1 \r\n
        # Type: Compute\r\n Manufacturer: HP\r\n
        # Product Name: ProLiant m500 Server Cartridge\r\n"
        node_info = mscm_driver.run_mscm_command(
            "show node info %s" % node_id, **params
        )
        match = re.search(r"Product Name:\s*([A-Za-z0-9 ]+)", node_info)
        if match is None:
            raise PowerFatalError(
                "MSCM Power Driver unable to extract node architecture"
                " from: %s" % node_info
            )
        else:
            cartridge = match.group(1)
        if cartridge in cartridge_mapping:
            arch = cartridge_mapping[cartridge]
        else:
            arch = cartridge_mapping["Default"]
        # Retrieve node MACs
        #
        # Example of output from running "show node macaddr <node_id>":
        # "show node macaddr c1n1\r\r\nSlot ID    NIC 1 (Switch A)
        # NIC 2 (Switch B)  NIC 3 (Switch A)  NIC 4 (Switch B)\r\n
        # ---- ----- ----------------- ----------------- -----------------
        # -----------------\r\n  1  c1n1  a0:1d:48:b5:04:34 a0:1d:48:b5:04:35
        # a0:1d:48:b5:04:36 a0:1d:48:b5:04:37\r\n\r\n\r\n"
        node_macaddr = mscm_driver.run_mscm_command(
            "show node macaddr %s" % node_id, **params
        )
        macs = re.findall(r":".join(["[0-9a-f]{2}"] * 6), node_macaddr)
        # Create node
        system_id = create_node(macs, arch, "mscm", params, domain).wait(30)

        if accept_all:
            commission_node(system_id, user).wait(30)
