# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Proxmox power driver implementation."""

import logging
import requests

logger = logging.getLogger("maas-power-driver-proxmox")


class ProxmoxPowerDriver:
    """Proxmox power driver using the Proxmox API."""

    def _get_session(self, context: dict) -> requests.Session:
        """Create an authenticated Proxmox session."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"https://{power_address}"

        power_user = context.get("power_user", "root@pam")
        power_pass = context.get("power_pass", "")

        session = requests.Session()
        session.verify = False  # Proxmox uses self-signed certs by default

        # Login to get ticket
        login_url = f"{power_address.rstrip('/')}/api2/json/access/ticket"
        resp = session.post(login_url, data={
            "username": power_user,
            "password": power_pass,
        }, timeout=30)
        resp.raise_for_status()

        ticket = resp.json()["data"]["ticket"]
        session.headers["CSRFPreventionToken"] = ticket
        self._base_url = power_address.rstrip("/")
        return session

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            session = self._get_session(context)
            node = context.get("power_node", "pve")
            vmid = context.get("vmid", "")
            if not vmid:
                raise ValueError("Missing 'vmid' in context")

            resp = session.get(
                f"{self._base_url}/api2/json/nodes/{node}/qemu/{vmid}/status",
                timeout=30
            )
            resp.raise_for_status()
            status = resp.json()["data"].get("status", "unknown")
            return "on" if status == "running" else "off"
        except Exception as e:
            logger.error("Proxmox query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        node = context.get("power_node", "pve")
        vmid = context.get("vmid", "")
        session.post(
            f"{self._base_url}/api2/json/nodes/{node}/qemu/{vmid}/status/start",
            timeout=30
        )

    def off(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        node = context.get("power_node", "pve")
        vmid = context.get("vmid", "")
        session.post(
            f"{self._base_url}/api2/json/nodes/{node}/qemu/{vmid}/status/shutdown",
            timeout=30
        )

    def cycle(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        node = context.get("power_node", "pve")
        vmid = context.get("vmid", "")
        session.post(
            f"{self._base_url}/api2/json/nodes/{node}/qemu/{vmid}/status/restart",
            timeout=30
        )

    def reset(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        node = context.get("power_node", "pve")
        vmid = context.get("vmid", "")
        session.post(
            f"{self._base_url}/api2/json/nodes/{node}/qemu/{vmid}/status/reset",
            timeout=30
        )

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the Proxmox driver")
