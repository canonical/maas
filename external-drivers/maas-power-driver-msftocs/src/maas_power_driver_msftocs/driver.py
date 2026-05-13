# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Microsoft OCS power driver implementation."""

import logging
import subprocess

logger = logging.getLogger("maas-power-driver-msftocs")


class MicrosoftOCSPowerDriver:
    """Microsoft OCS power driver using ocssmd tools."""

    def _run_ocs(self, context: dict, action: str) -> str:
        """Run an OCS management command."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        # Use ocssmd CLI if available, otherwise fall back to curl
        cmd = [
            "curl", "-s", "-k",
            "-u", f"{power_user}:{power_pass}",
            f"https://{power_address}/ocs/api/v1/power/{action}",
        ]

        logger.debug("Running OCS command: %s", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"OCS command failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            output = self._run_ocs(context, "status")
            if "on" in output.lower():
                return "on"
            elif "off" in output.lower():
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("MSFTOCS query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        self._run_ocs(context, "on")

    def off(self, system_id: str, context: dict) -> None:
        self._run_ocs(context, "off")

    def cycle(self, system_id: str, context: dict) -> None:
        self._run_ocs(context, "cycle")

    def reset(self, system_id: str, context: dict) -> None:
        self._run_ocs(context, "reset")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the MSFTOCS driver")
