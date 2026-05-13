# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""OpenBMC power driver implementation."""

import logging
import requests

logger = logging.getLogger("maas-power-driver-openbmc")


class OpenBMCPowerDriver:
    """OpenBMC power driver using the OpenBMC REST API."""

    def _get_session(self, context: dict) -> requests.Session:
        """Create an authenticated OpenBMC session."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"https://{power_address}"

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        session = requests.Session()
        session.verify = context.get("power_verify_ssl", True)

        # Login to get session token
        login_url = f"{power_address.rstrip('/')}/login"
        resp = session.post(login_url, json={
            "username": power_user,
            "password": power_pass,
        }, timeout=30)
        resp.raise_for_status()

        # Store session cookies
        self._base_url = power_address.rstrip("/")
        return session

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            session = self._get_session(context)
            resp = session.get(
                f"{self._base_url}/host/status", timeout=30
            )
            resp.raise_for_status()
            state = resp.json().get("status", "unknown").lower()
            if "on" in state:
                return "on"
            elif "off" in state:
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("OpenBMC query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system."""
        session = self._get_session(context)
        session.post(
            f"{self._base_url}/host/power",
            json={"action": "HostOn"}, timeout=30
        )

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        session = self._get_session(context)
        session.post(
            f"{self._base_url}/host/power",
            json={"action": "HostSoftOff"}, timeout=30
        )

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power."""
        session = self._get_session(context)
        session.post(
            f"{self._base_url}/host/power",
            json={"action": "HostCycle"}, timeout=30
        )

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        session = self._get_session(context)
        session.post(
            f"{self._base_url}/host/power",
            json={"action": "HostReset"}, timeout=30
        )

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the OpenBMC driver")
