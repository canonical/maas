# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Raritan power driver implementation using standard library."""

import logging

logger = logging.getLogger("maas-power-driver-raritan")


class RaritanPowerDriver:
    """Raritan power driver.

    Interfaces with Raritan-compatible BMCs.
    """

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement Raritan power state query
        raise NotImplementedError("Raritan query not yet implemented")

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement Raritan power on
        raise NotImplementedError("Raritan power on not yet implemented")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement Raritan power off
        raise NotImplementedError("Raritan power off not yet implemented")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on) with optional delay."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement Raritan power cycle
        raise NotImplementedError("Raritan power cycle not yet implemented")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement Raritan reset
        raise NotImplementedError("Raritan reset not yet implemented")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set the boot order for the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement Raritan boot order setting
        raise NotImplementedError("Raritan set boot order not yet implemented")
