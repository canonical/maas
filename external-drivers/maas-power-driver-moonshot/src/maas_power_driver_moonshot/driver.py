# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""HP Moonshot power driver implementation."""

import logging
import subprocess

logger = logging.getLogger("maas-power-driver-moonshot")


class MoonshotIPMIPowerDriver:
    """HP Moonshot power driver using ipmitool."""

    def _run_ipmitool(self, context: dict, *args: str) -> str:
        """Run an ipmitool command."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        cmd = ["ipmitool", "-I", "lanplus", "-H", power_address]
        if power_user:
            cmd.extend(["-U", power_user])
        if power_pass:
            cmd.extend(["-P", power_pass])
        cmd.extend(args)

        logger.debug("Running ipmitool: %s", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ipmitool failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            output = self._run_ipmitool(context, "chassis", "power", "status")
            if "on" in output.lower():
                return "on"
            elif "off" in output.lower():
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("Moonshot query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        self._run_ipmitool(context, "chassis", "power", "on")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        self._run_ipmitool(context, "chassis", "power", "off")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power."""
        self._run_ipmitool(context, "chassis", "power", "cycle")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        self._run_ipmitool(context, "chassis", "power", "reset")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set boot order (not supported by Moonshot)."""
        logger.warning("set_boot_order is not supported by the Moonshot driver")
