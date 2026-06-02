# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Powertek Power Driver.

Support for managing Powertek PDU outlets via SNMP.
"""

import re

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerActionError, PowerDriver
from provisioningserver.utils import shell


class PowertekState:
    ON = "2"


class PowertekPDVersion:
    VERSION_1 = "1"
    VERSION_2 = "2"


POWERTEK_PDU_VERSION_CHOICES = [
    [PowertekPDVersion.VERSION_1, "Version 1"],
    [PowertekPDVersion.VERSION_2, "Version 2"],
]

POWERTEK_PDU_VERSION_1_QUERY_OID = "1.3.6.1.4.1.42610.1.4.1.1.2.2"
POWERTEK_PDU_VERSION_1_CONTROL_OID = "1.3.6.1.4.1.42610.1.4.1.1.3.2"
POWERTEK_PDU_VERSION_2_OID = "1.3.6.1.4.1.42610.1.3"


class PowertekPowerDriver(PowerDriver):
    name = "powertek"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "Powertek PDU"
    settings = [
        make_setting_field(
            "power_address",
            "IP for Powertek PDU",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field(
            "pdu_number",
            "PDU (1-16)",
            default="1",
            required=True,
        ),
        make_setting_field(
            "node_outlet",
            "Outlet (1-72)",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "power_community",
            "SNMP Write community",
            default="private",
            required=True,
        ),
        make_setting_field(
            "pdu_version",
            "PDU version",
            field_type="choice",
            choices=POWERTEK_PDU_VERSION_CHOICES,
            default=PowertekPDVersion.VERSION_1,
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
                "Powertek Power Driver external process error for command %s: %s"
                % ("".join(command), result.stderr)
            )
        match = re.search(r"INTEGER:\s*([0-9]+)", result.stdout)
        if match is None:
            raise PowerActionError(
                "Powertek Power Driver unable to extract outlet power state"
                " from: %s" % result.stdout
            )
        else:
            return match.group(1)

    def power_on(self, system_id, context):
        """Power on Powertek outlet."""
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
        self.run_process(
            "snmpset",
            *_get_common_args(context, is_query=False),
            "i",
            "2",
        )

    def power_off(self, system_id, context):
        """Power off Powertek outlet."""
        off_value = (
            "4"
            if _get_pdu_version(context) == PowertekPDVersion.VERSION_1
            else "1"
        )
        self.run_process(
            "snmpset",
            *_get_common_args(context, is_query=False),
            "i",
            off_value,
        )

    def power_query(self, system_id, context):
        """Power query Powertek outlet."""
        power_state = self.run_process(
            "snmpget",
            *_get_common_args(context, is_query=True),
        )
        if power_state == PowertekState.ON:
            return "on"
        return "off"

    def power_reset(self, system_id, context):
        """Power reset Powertek outlet."""
        raise NotImplementedError()


def _get_pdu_version(context):
    pdu_version = context.get("pdu_version", PowertekPDVersion.VERSION_1)
    if pdu_version not in {
        PowertekPDVersion.VERSION_1,
        PowertekPDVersion.VERSION_2,
    }:
        raise PowerActionError(
            "Powertek Power Driver received unsupported PDU version: %r"
            % pdu_version
        )
    return pdu_version


def _get_common_args(context, is_query):
    address = context["power_address"]
    outlet = context["node_outlet"]
    pdu_number = context.get("pdu_number", "1")
    community = context.get("power_community", "private")
    pdu_version = _get_pdu_version(context)

    if pdu_version == PowertekPDVersion.VERSION_1:
        oid = (
            f".{POWERTEK_PDU_VERSION_1_QUERY_OID}.{pdu_number}.2.1.5.{outlet}"
            if is_query
            else f".{POWERTEK_PDU_VERSION_1_CONTROL_OID}.{pdu_number}.2.1.14.{outlet}"
        )
    else:
        oid = f".{POWERTEK_PDU_VERSION_2_OID}.{pdu_number}.2.1.3.{outlet}"

    return [
        "-c",
        community,
        "-v1",
        address,
        oid,
    ]