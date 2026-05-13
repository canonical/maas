# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Cisco UCSM power driver implementation."""

import logging
import requests

logger = logging.getLogger("maas-power-driver-ucsm")


class UCSMPowerDriver:
    """Cisco UCS Manager power driver."""

    def _get_session(self, context: dict) -> requests.Session:
        """Create an authenticated UCSM session."""
        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        if not power_address.startswith("http"):
            power_address = f"https://{power_address}"

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        session = requests.Session()
        session.verify = False  # UCSM uses self-signed certs
        self._base_url = f"{power_address.rstrip('/')}/nuova"

        # Login via UCSM REST API
        login_xml = f'<aaaLogin inName="{power_user}" inPassword="{power_pass}"/>'
        resp = session.post(f"{self._base_url}/mo", data=login_xml, timeout=30)
        resp.raise_for_status()
        return session

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            session = self._get_session(context)
            server_label = context.get("server_label", "")
            if not server_label:
                raise ValueError("Missing 'server_label' in context")

            query_xml = f'<configResolveClass className="computeBlade" inHierarchical="true"/>'
            resp = session.post(f"{self._base_url}/mo", data=query_xml, timeout=30)
            resp.raise_for_status()

            if "admin-power-off" in resp.text:
                return "off"
            elif "admin-power-on" in resp.text:
                return "on"
            return "unknown"
        except Exception as e:
            logger.error("UCSM query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        server_label = context.get("server_label", "")
        power_xml = f'<configConfMo dn="servers/{server_label}" inConfig="<computeRackUnit adminPower=\"admin-power-on\""/>'
        session.post(f"{self._base_url}/mo", data=power_xml, timeout=30)

    def off(self, system_id: str, context: dict) -> None:
        session = self._get_session(context)
        server_label = context.get("server_label", "")
        power_xml = f'<configConfMo dn="servers/{server_label}" inConfig="<computeRackUnit adminPower=\"admin-power-off\""/>'
        session.post(f"{self._base_url}/mo", data=power_xml, timeout=30)

    def cycle(self, system_id: str, context: dict) -> None:
        self.off(system_id, context)
        self.on(system_id, context)

    def reset(self, system_id: str, context: dict) -> None:
        self.on(system_id, context)

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the UCSM driver")
