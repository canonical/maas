# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""APC power driver implementation using snmp."""

import logging
import re
import subprocess
import time

logger = logging.getLogger("maas-power-driver-apc")

# APC NetBotz/APSNet MIB base OID
APC_HARDWARE_OID = "1.3.6.1.4.1.318.1.1"

# PDU type suffixes for outlet OID
APC_PDU_TYPE_RPDU = "RPDU"
APC_PDU_TYPE_MASTERSWITCH = "MASTERSWITCH"

APC_PDU_TYPE_OUTLET_SUFFIX = {
    APC_PDU_TYPE_RPDU: "12.3.3.1.1.4",
    APC_PDU_TYPE_MASTERSWITCH: "4.4.2.1.3",
}

# Outlet power state values (from SNMP response)
APC_STATE_ON = "1"
APC_STATE_OFF = "2"

# Power control action values
APC_ACTION_TURN_ON = "1"
APC_ACTION_SHUTDOWN = "2"


class APCPowerDriver:
    """APC power driver using SNMP.

    Interfaces with American Power Conversion (APC) PDU outlets via SNMP v1.
    Supports both rPDU and MasterSwitch PDU types.
    """

    def _build_oid(self, context):
        """Build the full SNMP OID for the outlet."""
        outlet = context.get("node_outlet")
        if not outlet:
            raise ValueError("Missing 'node_outlet' in context")

        pdu_type = context.get("pdu_type", APC_PDU_TYPE_RPDU)
        suffix = APC_PDU_TYPE_OUTLET_SUFFIX.get(pdu_type)
        if not suffix:
            raise ValueError(f"Unknown PDU type: {pdu_type}")

        return f".{APC_HARDWARE_OID}.{suffix}.{outlet}"

    def _run_snmp(self, command, context, *extra_args):
        """Run an SNMP command and parse the result.

        Returns the INTEGER value from the SNMP response.
        """
        address = context.get("power_address")
        if not address:
            raise ValueError("Missing 'power_address' in context")

        oid = self._build_oid(context)

        cmd = [
            command,
            "-c", "private",
            "-v1",
            address,
            oid,
        ]
        cmd.extend(extra_args)

        logger.debug("Running SNMP command: %s", cmd)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"APC SNMP command failed: {result.stderr.strip()}"
            )

        # Parse INTEGER value from snmpget output
        match = re.search(r"INTEGER:\s*([1-2])", result.stdout)
        if match is None:
            raise RuntimeError(
                f"Unable to extract outlet power state from: {result.stdout}"
            )
        return match.group(1)

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the APC outlet.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        try:
            power_state = self._run_snmp("snmpget", context)
            if power_state == APC_STATE_ON:
                return "on"
            elif power_state == APC_STATE_OFF:
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("APC query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the APC outlet.

        If the outlet is already on, powers it off first (cycle behavior
        matching the monorepo driver), then applies the configured delay
        before turning it back on.
        """
        try:
            current_state = self._run_snmp("snmpget", context)
            if current_state == APC_STATE_ON:
                # Already on - cycle it (off then on)
                self._run_snmp("snmpset", context, "i", APC_ACTION_SHUTDOWN)
            else:
                # Apply delay before powering on
                delay = float(context.get("power_on_delay", "5"))
                time.sleep(delay)
            self._run_snmp("snmpset", context, "i", APC_ACTION_TURN_ON)
        except Exception as e:
            logger.error("APC power on failed: %s", e)
            raise

    def off(self, system_id: str, context: dict) -> None:
        """Power off the APC outlet."""
        try:
            self._run_snmp("snmpset", context, "i", APC_ACTION_SHUTDOWN)
        except Exception as e:
            logger.error("APC power off failed: %s", e)
            raise

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on)."""
        try:
            self._run_snmp("snmpset", context, "i", APC_ACTION_SHUTDOWN)
            delay = float(context.get("power_on_delay", "5"))
            time.sleep(delay)
            self._run_snmp("snmpset", context, "i", APC_ACTION_TURN_ON)
        except Exception as e:
            logger.error("APC power cycle failed: %s", e)
            raise

    def reset(self, system_id: str, context: dict) -> None:
        """Reset the APC outlet.

        APC PDUs do not support a native reset action, so this performs
        a cycle (off then on) as the closest equivalent.
        """
        try:
            self._run_snmp("snmpset", context, "i", APC_ACTION_SHUTDOWN)
            delay = float(context.get("power_on_delay", "5"))
            time.sleep(delay)
            self._run_snmp("snmpset", context, "i", APC_ACTION_TURN_ON)
        except Exception as e:
            logger.error("APC reset failed: %s", e)
            raise

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set boot order (not supported by APC PDU).

        APC PDUs control power outlets, not boot configuration.
        """
        logger.warning("set_boot_order is not supported by the APC driver")
