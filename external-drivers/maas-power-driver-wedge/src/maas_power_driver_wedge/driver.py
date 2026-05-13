# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""HP Power Distribution Unit Wedge power driver implementation."""

import logging
import subprocess

logger = logging.getLogger("maas-power-driver-wedge")


class WedgePowerDriver:
    """HP Power Distribution Unit Wedge power driver using wget."""

    def _run_wget(self, context: dict, action: str) -> str:
        """Run a wget command to the Wedge PDU."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"http://{power_address}"

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")
        outlet = context.get("outlet", "1")

        url = f"{power_address.rstrip('/')}/cgi-bin/power.cgi?{action}&outlet={outlet}"
        cmd = ["wget", "-qO-", url, "--timeout=30"]
        if power_user and power_pass:
            cmd.extend(["--user", power_user, "--password", power_pass])

        logger.debug("Running wget: %s", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.returncode != 0:
            raise RuntimeError(f"wget failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            output = self._run_wget(context, "status")
            if "on" in output.lower():
                return "on"
            elif "off" in output.lower():
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("Wedge query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        self._run_wget(context, "on")

    def off(self, system_id: str, context: dict) -> None:
        self._run_wget(context, "off")

    def cycle(self, system_id: str, context: dict) -> None:
        self._run_wget(context, "cycle")

    def reset(self, system_id: str, context: dict) -> None:
        self._run_wget(context, "reset")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the Wedge driver")
