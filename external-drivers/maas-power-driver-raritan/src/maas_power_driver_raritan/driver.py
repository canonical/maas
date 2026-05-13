# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Raritan power driver implementation."""

import logging
import requests

logger = logging.getLogger("maas-power-driver-raritan")


class RaritanPowerDriver:
    """Raritan power driver using the Raritan PX series PDU API."""

    def _get_session(self, context: dict) -> requests.Session:
        """Create an authenticated Raritan session."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"https://{power_address}"

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        session = requests.Session()
        session.auth = (power_user, power_pass)
        session.verify = context.get("power_verify_ssl", True)
        self._base_url = power_address.rstrip("/")
        return session

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            session = self._get_session(context)
            outlet = context.get("outlet", "1")
            resp = session.get(
                f"{self._base_url}/api/v1/outlets/{outlet}", timeout=30
            )
            resp.raise_for_status()
            state = resp.json().get("state", "unknown")
            if state in ("on", "closed"):
                return "on"
            elif state in ("off", "open"):
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("Raritan query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        outlet = context.get("outlet", "1")
        session.put(
            f"{self._base_url}/api/v1/outlets/{outlet}/close", timeout=30
        )

    def off(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        outlet = context.get("outlet", "1")
        session.put(
            f"{self._base_url}/api/v1/outlets/{outlet}/open", timeout=30
        )

    def cycle(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        outlet = context.get("outlet", "1")
        session.put(
            f"{self._base_url}/api/v1/outlets/{outlet}/cycle", timeout=30
        )

    def reset(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        outlet = context.get("outlet", "1")
        session.put(
            f"{self._base_url}/api/v1/outlets/{outlet}/close", timeout=30
        )

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the Raritan driver")
