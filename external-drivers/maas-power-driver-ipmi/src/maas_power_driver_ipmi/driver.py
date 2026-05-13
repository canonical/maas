# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""IPMI power driver implementation using freeipmi-tools."""

import logging

logger = logging.getLogger("maas-power-driver-ipmi")


class IPMIPowerDriver:
    """IPMI power driver that interfaces with BMCs via IPMI commands.

    Uses freeipmi-tools (ipmiutil or ipmitool) to communicate with
    IPMI-compatible baseboard management controllers.
    """

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IPMI power state query
        # e.g., subprocess.run(["ipmitool", "-H", power_address, ...])
        raise NotImplementedError("IPMI query not yet implemented")

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IPMI power on
        raise NotImplementedError("IPMI power on not yet implemented")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IPMI power off
        raise NotImplementedError("IPMI power off not yet implemented")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on) with optional delay."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IPMI power cycle
        raise NotImplementedError("IPMI power cycle not yet implemented")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IPMI reset
        raise NotImplementedError("IPMI reset not yet implemented")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set the boot order for the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IPMI boot order setting
        raise NotImplementedError("IPMI set boot order not yet implemented")
