# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""IBM HMCz (z/OS) power driver implementation."""

import logging

logger = logging.getLogger("maas-power-driver-hmcz")


class HMCZPowerDriver:
    """IBM HMCz power driver for z/OS LPARs using zhmcclient."""

    def _get_lpar(self, context: dict):
        """Get the HMC LPAR object."""
        try:
            from zhmcclient import Client
        except ImportError:
            raise RuntimeError("python3-zhmcclient package is not installed")

        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        hmc = Client(power_address)
        hmc.login_with_password(power_user, password=power_pass)

        lpar_name = context.get("lpar_name", "")
        if not lpar_name:
            raise ValueError("Missing 'lpar_name' in context")

        cpc_name = context.get("cpc_name", "")
        if cpc_name:
            cpc = hmc.cpcs.name(cpc_name)
        else:
            cpcs = hmc.cpcs.list()
            if not cpcs:
                raise RuntimeError("No CPCs found")
            cpc = cpcs[0]

        lpar = cpc.lpars.name(lpar_name)
        return hmc, cpc, lpar

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            hmc, cpc, lpar = self._get_lpar(context)
            try:
                props = lpar.properties
                state = props.get("status", "unknown")
                state_map = {
                    "blocking": "off",
                    "deactivated": "off",
                    "deactivating": "off",
                    "not-defined": "off",
                    "powered-off": "off",
                    "powering-on": "on",
                    "powered-on": "on",
                    "powering-off": "off",
                    "stored": "off",
                }
                return state_map.get(state, "unknown")
            finally:
                hmc.logout()
        except Exception as e:
            logger.error("HMCz query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the LPAR."""
        hmc, cpc, lpar = self._get_lpar(context)
        try:
            lpar.open()
        finally:
            hmc.logout()

    def off(self, system_id: str, context: dict) -> None:
        """Power off the LPAR."""
        hmc, cpc, lpar = self._get_lpar(context)
        try:
            lpar.close()
        finally:
            hmc.logout()

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power."""
        hmc, cpc, lpar = self._get_lpar(context)
        try:
            lpar.close()
            lpar.open()
        finally:
            hmc.logout()

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the LPAR."""
        hmc, cpc, lpar = self._get_lpar(context)
        try:
            lpar.close()
            lpar.open()
        finally:
            hmc.logout()

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set boot order (not supported by HMCz driver)."""
        logger.warning("set_boot_order is not supported by the HMCz driver")
