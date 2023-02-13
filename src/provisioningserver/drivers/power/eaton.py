"""Eaton Power Driver.

Support for managing Eaton PDU outlets via SNMP.
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


class EatonState:
    OFF = "0"
    ON = "1"


class EatonFunction:
    QUERY = "2"
    OFF = "3"
    ON = "4"


class EatonPowerDriver(PowerDriver):
    name = "eaton"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "Eaton PDU"
    settings = [
        make_setting_field("power_address", "IP for Eaton PDU", required=True),
        make_setting_field(
            "node_outlet",
            "Eaton PDU node outlet number (1-24)",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "power_on_delay", "Power ON outlet delay (seconds)", default="5"
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")
    queryable = True

    def detect_missing_packages(self):
        if not shell.has_command_available("snmpget"):
            return ["snmp"]
        return []

    def run_process(self, *command):
        """Run SNMP command in subprocess."""
        result = shell.run_command(*command)
        if result.returncode != 0:
            raise PowerActionError(
                "Eaton Power Driver external process error for command %s: %s"
                % ("".join(command), result.stderr)
            )
        match = re.search(r"INTEGER:\s*([0-1])", result.stdout)
        if match is None:
            raise PowerActionError(
                "Eaton Power Driver unable to extract outlet power state"
                " from: %s" % result.stdout
            )
        else:
            return match.group(1)

    def power_on(self, system_id, context):
        """Power on Eaton outlet."""
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
        sleep(float(context["power_on_delay"]))
        self.run_process(
            "snmpset",
            *_get_common_args(
                context["power_address"],
                EatonFunction.ON,
                context["node_outlet"],
            ),
            "i",
            "0",
        )

    def power_off(self, system_id, context):
        """Power off Eaton outlet."""
        self.run_process(
            "snmpset",
            *_get_common_args(
                context["power_address"],
                EatonFunction.OFF,
                context["node_outlet"],
            ),
            "i",
            "0",
        )

    def power_query(self, system_id, context):
        """Power query for Eaton outlet."""
        power_state = self.run_process(
            "snmpget",
            *_get_common_args(
                context["power_address"],
                EatonFunction.QUERY,
                context["node_outlet"],
            ),
        )
        if power_state == EatonState.OFF:
            return "off"
        elif power_state == EatonState.ON:
            return "on"
        else:
            raise PowerActionError(
                "Eaton Power Driver retrieved unknown power state: %r"
                % power_state
            )


def _get_common_args(address, function, outlet):
    return [
        "-c",
        "private",
        "-v1",
        address,
        f"1.3.6.1.4.1.534.6.6.7.6.6.1.{function}.0.{outlet}",
    ]
