# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""IBM MSCM power driver implementation."""

import logging

logger = logging.getLogger("maas-power-driver-mscm")


class MSCMPowerDriver:
    """IBM MSCM power driver using zhmcclient."""

    def _get_partition(self, context: dict):
        """Get the MSCM partition object."""
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

        partition_name = context.get("partition_name", "")
        if not partition_name:
            raise ValueError("Missing 'partition_name' in context")

        cpc_name = context.get("cpc_name", "")
        if cpc_name:
            cpc = hmc.cpcs.name(cpc_name)
        else:
            cpcs = hmc.cpcs.list()
            if not cpcs:
                raise RuntimeError("No CPCs found")
            cpc = cpcs[0]

        partition = cpc.partitions.name(partition_name)
        return hmc, cpc, partition

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        try:
            hmc, cpc, partition = self._get_partition(context)
            try:
                props = partition.properties
                state = props.get("status", "unknown")
                state_map = {
                    "not-activated": "off", "powering-on": "on",
                    "activating": "on", "active": "on",
                    "deactivating": "off", "powering-off": "off",
                }
                return state_map.get(state, "unknown")
            finally:
                hmc.logout()
        except Exception as e:
            logger.error("MSCM query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        hmc, cpc, partition = self._get_partition(context)
        try:
            partition.activate()
        finally:
            hmc.logout()

    def off(self, system_id: str, context: dict) -> None:
        hmc, cpc, partition = self._get_partition(context)
        try:
            partition.deactivate(force=False)
        finally:
            hmc.logout()

    def cycle(self, system_id: str, context: dict) -> None:
        hmc, cpc, partition = self._get_partition(context)
        try:
            partition.deactivate(force=True)
            partition.activate()
        finally:
            hmc.logout()

    def reset(self, system_id: str, context: dict) -> None:
        hmc, cpc, partition = self._get_partition(context)
        try:
            partition.deactivate(force=True)
            partition.activate()
        finally:
            hmc.logout()

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the MSCM driver")
