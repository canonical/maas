# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""DLI power driver implementation."""

import logging
import subprocess

logger = logging.getLogger("maas-power-driver-dli")


class DLIPowerDriver:
    """DLI power driver using wget to communicate with DLI BMCs."""

    def _run_wget(self, context: dict, action: str) -> str:
        """Run a wget command to the DLI BMC."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"http://{power_address}"

        url = f"{power_address.rstrip('/')}/{action}"
        cmd = ["wget", "-qO-", url, "--timeout=30"]

        logger.debug("Running wget: %s", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.returncode != 0:
            raise RuntimeError(f"wget failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            output = self._run_wget(context, "status.cgi")
            if "on" in output.lower():
                return "on"
            elif "off" in output.lower():
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("DLI query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        self._run_wget(context, "power.cgi?on")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        self._run_wget(context, "power.cgi?off")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power."""
        self._run_wget(context, "power.cgi?cycle")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        self._run_wget(context, "power.cgi?reset")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set boot order (not supported by DLI)."""
        logger.warning("set_boot_order is not supported by the DLI driver")
