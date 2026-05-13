# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""SeaMicro power driver implementation."""

import logging

logger = logging.getLogger("maas-power-driver-seamicro")


class SeaMicroPowerDriver:
    """SeaMicro power driver using seamicroclient."""

    def _get_client(self, context: dict):
        """Create a SeaMicro client connection."""
        try:
            from seamicroclient import SeaMicroClient
        except ImportError:
            raise RuntimeError("python3-seamicroclient package is not installed")

        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        client = SeaMicroClient(power_address, power_user, power_pass)
        return client

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            client = self._get_client(context)
            blade_id = context.get("blade_id", "")
            if not blade_id:
                raise ValueError("Missing 'blade_id' in context")

            state = client.get_blade_state(blade_id)
            state_map = {
                "ON": "on", "OFF": "off", "STANDBY": "off",
                "BOOT": "on", "SHUTDOWN": "off",
            }
            return state_map.get(state, "unknown")
        except Exception as e:
            logger.error("SeaMicro query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        client = self._get_client(context)
        blade_id = context.get("blade_id", "")
        client.power_on(blade_id)

    def off(self, system_id: str, context: dict) -> None:
        client = self._get_client(context)
        blade_id = context.get("blade_id", "")
        client.power_off(blade_id)

    def cycle(self, system_id: str, context: dict) -> None:
        client = self._get_client(context)
        blade_id = context.get("blade_id", "")
        client.power_cycle(blade_id)

    def reset(self, system_id: str, context: dict) -> None:
        client = self._get_client(context)
        blade_id = context.get("blade_id", "")
        client.power_reset(blade_id)

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the SeaMicro driver")
