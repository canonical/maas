# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""IBM HMCz power driver implementation using python3-zhmcclient."""

import logging

logger = logging.getLogger("maas-power-driver-hmcz")


class HMCzPowerDriver:
    """IBM HMCz power driver.

    Interfaces with IBM HMCz-compatible BMCs.
    """

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMCz power state query
        raise NotImplementedError("IBM HMCz query not yet implemented")

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMCz power on
        raise NotImplementedError("IBM HMCz power on not yet implemented")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMCz power off
        raise NotImplementedError("IBM HMCz power off not yet implemented")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on) with optional delay."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMCz power cycle
        raise NotImplementedError("IBM HMCz power cycle not yet implemented")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMCz reset
        raise NotImplementedError("IBM HMCz reset not yet implemented")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set the boot order for the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMCz boot order setting
        raise NotImplementedError("IBM HMCz set boot order not yet implemented")
