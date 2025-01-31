# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""American Power Conversion (APC) Power Driver.

Support for managing American Power Conversion (APC) PDU outlets via SNMP.
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


class APCState:
    ON = "1"
    OFF = "2"


class APC_PDU_TYPE:
    RPDU = "RPDU"
    MASTERSWITCH = "MASTERSWITCH"


APC_PDU_TYPE_CHOICES = [
    [APC_PDU_TYPE.RPDU, "rPDU"],
    [APC_PDU_TYPE.MASTERSWITCH, "masterswitch"],
]

APC_HARDWARE_OID = "1.3.6.1.4.1.318.1.1"
APC_PDU_TYPE_OUTLET_SUFFIX = {
    APC_PDU_TYPE.RPDU: "12.3.3.1.1.4",
    APC_PDU_TYPE.MASTERSWITCH: "4.4.2.1.3",
}


class APCPowerDriver(PowerDriver):
    name = "apc"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "American Power Conversion (APC) PDU"
    settings = [
        make_setting_field(
            "power_address",
            "IP for APC PDU",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field(
            "node_outlet",
            "APC PDU node outlet number (1-16)",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "power_on_delay", "Power ON outlet delay (seconds)", default="5"
        ),
        make_setting_field(
            "pdu_type",
            "PDU type",
            field_type="choice",
            choices=APC_PDU_TYPE_CHOICES,
            # This was the first type the APC driver supported.
            default=APC_PDU_TYPE.RPDU,
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
                "APC Power Driver external process error for command %s: %s"
                % ("".join(command), result.stderr)
            )
        match = re.search(r"INTEGER:\s*([1-2])", result.stdout)
        if match is None:
            raise PowerActionError(
                "APC Power Driver unable to extract outlet power state"
                " from: %s" % result.stdout
            )
        else:
            return match.group(1)

    def power_on(self, system_id, context):
        """Power on Apc outlet."""
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
        sleep(float(context["power_on_delay"]))
        self.run_process(
            "snmpset",
            *_get_common_args(context),
            "i",
            "1",
        )

    def power_off(self, system_id, context):
        """Power off APC outlet."""
        self.run_process(
            "snmpset",
            *_get_common_args(context),
            "i",
            "2",
        )

    def power_query(self, system_id, context):
        """Power query APC outlet."""
        power_state = self.run_process(
            "snmpget",
            *_get_common_args(context),
        )
        if power_state == APCState.OFF:
            return "off"
        elif power_state == APCState.ON:
            return "on"
        else:
            raise PowerActionError(
                "APC Power Driver retrieved unknown power state: %r"
                % power_state
            )

    def power_reset(self, system_id, context):
        """Power reset APC outlet."""
        raise NotImplementedError()


def _get_common_args(context):
    address = context["power_address"]
    outlet = context["node_outlet"]
    pdu_type = context.get("pdu_type", APC_PDU_TYPE.RPDU)
    return [
        "-c",
        "private",
        "-v1",
        address,
        f".{APC_HARDWARE_OID}.{APC_PDU_TYPE_OUTLET_SUFFIX[pdu_type]}.{outlet}",
    ]
