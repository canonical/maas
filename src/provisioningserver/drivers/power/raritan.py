# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Raritan PDU Power Driver.

Support for managing Raritan PDU outlets via SNMP.
"""


import re
from time import sleep

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerActionError, PowerDriver
from provisioningserver.utils import shell


class RaritanState:
    ON = "1"
    OFF = "0"


class RaritanPowerDriver(PowerDriver):
    name = "raritan"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "Raritan PDU"
    settings = [
        make_setting_field(
            "power_address", "IP for Raritan PDU", required=True
        ),
        make_setting_field(
            "node_outlet",
            "Raritan PDU node outlet number",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "power_on_delay", "Power ON outlet delay (seconds)", default="5"
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        binary, package = ["snmpset", "snmp"]
        if not shell.has_command_available(binary):
            return [package]
        return []

    def run_process(self, *command):
        """Run SNMP command in subprocess."""
        result = shell.run_command(*command)
        if result.returncode != 0:
            raise PowerActionError(
                "Raritan Power Driver external process error for command %s: %s"
                % ("".join(command), result.stderr)
            )
        match = re.search(r"INTEGER:\s*([0-1])", result.stdout)
        if match is None:
            raise PowerActionError(
                "Raritan Power Driver unable to extract outlet power state"
                " from: %s" % result.stdout
            )
        else:
            return match.group(1)

    def power_on(self, system_id, context):
        """Power on Raritan outlet."""
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
        sleep(float(context["power_on_delay"]))
        self.run_process(
            "snmpset",
            *_get_common_args(
                context["power_address"], context["node_outlet"]
            ),
            "i",
            "1",
        )

    def power_off(self, system_id, context):
        """Power off Raritan outlet."""
        self.run_process(
            "snmpset",
            *_get_common_args(
                context["power_address"], context["node_outlet"]
            ),
            "i",
            "0",
        )

    def power_query(self, system_id, context):
        """Power query Raritan outlet."""
        power_state = self.run_process(
            "snmpget",
            *_get_common_args(
                context["power_address"], context["node_outlet"]
            ),
        )
        if power_state == RaritanState.OFF:
            return "off"
        elif power_state == RaritanState.ON:
            return "on"
        else:
            raise PowerActionError(
                "Raritan Power Driver retrieved unknown power state: %r"
                % power_state
            )


def _get_common_args(address, outlet):
    return [
        "-c",
        "private",
        "-v2c",
        address,
        f".1.3.6.1.4.1.13742.6.4.1.2.1.2.1.{outlet}",
    ]
