# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Eaton power driver implementation."""

import logging
import subprocess

logger = logging.getLogger("maas-power-driver-eaton")


class EatonPowerDriver:
    """Eaton power driver using wget/curl to communicate with Eaton BMCs."""

    def _run_command(self, context: dict, action: str) -> str:
        """Run a command to the Eaton BMC."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"http://{power_address}"

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        url = f"{power_address.rstrip('/')}/cgi-bin/cgi?cmd=set_power_state&state={action}"
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
            power_address = context.get("power_address")
            if not power_address:
                raise ValueError("Missing 'power_address' in context")
            if not power_address.startswith("http"):
                power_address = f"http://{power_address}"

            cmd = [
                "wget",
                "-qO-",
                f"{power_address.rstrip('/')}/cgi-bin/cgi?cmd=get_power_state",
                "--timeout=30",
            ]
            power_user = context.get("power_user", "")
            power_pass = context.get("power_pass", "")
            if power_user and power_pass:
                cmd.extend(["--user", power_user, "--password", power_pass])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if result.returncode != 0:
                raise RuntimeError(f"wget failed: {result.stderr.strip()}")

            output = result.stdout.strip()
            if "on" in output.lower():
                return "on"
            elif "off" in output.lower():
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("Eaton query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        self._run_command(context, "on")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        self._run_command(context, "off")

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power."""
        self._run_command(context, "cycle")

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        self._run_command(context, "reset")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set boot order (not supported by Eaton)."""
        logger.warning("set_boot_order is not supported by the Eaton driver")
