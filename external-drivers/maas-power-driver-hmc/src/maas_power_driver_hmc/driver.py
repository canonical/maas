# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""IBM HMC power driver implementation using python3-zhmcclient."""

import logging

logger = logging.getLogger("maas-power-driver-hmc")


class HMCPowerDriver:
    """IBM HMC power driver.

    Interfaces with IBM HMC-compatible BMCs.
    """

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMC power state query
        raise NotImplementedError("IBM HMC query not yet implemented")

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMC power on
        raise NotImplementedError("IBM HMC power on not yet implemented")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMC power off
        raise NotImplementedError("IBM HMC power off not yet implemented")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on) with optional delay."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMC power cycle
        raise NotImplementedError("IBM HMC power cycle not yet implemented")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMC reset
        raise NotImplementedError("IBM HMC reset not yet implemented")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set the boot order for the system."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        # TODO: Implement IBM HMC boot order setting
        raise NotImplementedError("IBM HMC set boot order not yet implemented")
