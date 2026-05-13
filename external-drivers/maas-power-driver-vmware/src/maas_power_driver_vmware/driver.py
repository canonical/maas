# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""VMware power driver implementation using python3-pyvmomi."""

import logging

logger = logging.getLogger("maas-power-driver-vmware")


class VMwarePowerDriver:
    """VMware power driver.

    Interfaces with VMware-compatible BMCs.
    """

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement VMware power state query
        raise NotImplementedError("VMware query not yet implemented")

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement VMware power on
        raise NotImplementedError("VMware power on not yet implemented")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement VMware power off
        raise NotImplementedError("VMware power off not yet implemented")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on) with optional delay."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement VMware power cycle
        raise NotImplementedError("VMware power cycle not yet implemented")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement VMware reset
        raise NotImplementedError("VMware reset not yet implemented")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set the boot order for the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement VMware boot order setting
        raise NotImplementedError("VMware set boot order not yet implemented")
