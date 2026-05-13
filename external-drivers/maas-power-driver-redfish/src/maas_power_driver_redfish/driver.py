# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Redfish power driver implementation using python3-requests."""

import json
import logging
import time
from urllib.parse import urljoin

import requests

logger = logging.getLogger("maas-power-driver-redfish")

REDFISH_SYSTEMS_ENDPOINT = "redfish/v1/Systems"
REDFISH_POWER_CONTROL_ENDPOINT = "redfish/v1/Systems/%s/Actions/ComputerSystem.Reset"

MAX_REQUEST_RETRIES = 5
MAX_STATUS_REQUEST_RETRIES = 7

# Redfish ResetType values
POWER_CHANGE_ON = "On"
POWER_CHANGE_OFF = "ForceOff"
POWER_CHANGE_RESET = "GracefulRestart"
POWER_CHANGE_CYCLE = "ForceRestart"

# Boot override values
BOOT_SOURCE_PXE = "Pxe"
BOOT_SOURCE_OVERRIDE_ENABLED = "Once"

# Power state mapping from Redfish to MAAS
# Redfish states: Off, On, Paused, PoweringOff, PoweringOn, StandaloneNetworking, etc.
POWER_STATE_MAP = {
    "off": "off",
    "poweringon": "off",
    "on": "on",
    "paused": "on",
    "poweringoff": "on",
    "standalonenetworking": "on",
}


class RedfishPowerDriver:
    """Redfish power driver.

    Interfaces with Redfish-compatible BMCs using HTTP requests.
    """

    def _get_url(self, context):
        """Return the base URL for the Redfish BMC."""
        url = context.get("power_address")
        if not url:
            raise ValueError("Missing 'power_address' in context")
        if "https" not in url and "http" not in url:
            url = f"https://{url}"
        return url.rstrip("/")

    def _make_session(self, context):
        """Create an authenticated requests session."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "MAAS",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")
        if power_user or power_pass:
            session.auth = (power_user, power_pass)

        # Handle SSL verification
        verify_ssl = context.get("power_verify_ssl", True)
        if isinstance(verify_ssl, str):
            verify_ssl = verify_ssl.lower() not in ("false", "no", "0")
        session.verify = verify_ssl

        return session

    def _redfish_request(self, session, method, path, body=None, url_base=None):
        """Make a Redfish API request with retry logic and exponential backoff."""
        retries = 0
        sleep_time = 0
        last_exception = None

        while True:
            time.sleep(sleep_time)
            try:
                full_url = urljoin(url_base, path)
                resp = session.request(
                    method, full_url, json=body, timeout=30
                )
                resp.raise_for_status()
                if resp.content:
                    return resp.json()
                return {}
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (401, 403):
                    logger.error(
                        "Power action fatal error (auth) for method '%s' on path '%s'",
                        method, path,
                    )
                    raise RuntimeError(
                        f"Authentication failed for Redfish request: {e}"
                    ) from e
                last_exception = e
            except Exception as e:
                last_exception = e

            if retries >= MAX_REQUEST_RETRIES:
                logger.error(
                    "Maximum retries (%d) reached for '%s' on '%s'",
                    MAX_REQUEST_RETRIES, method, path,
                )
                raise RuntimeError(
                    f"Redfish request failed after {MAX_REQUEST_RETRIES} retries: {last_exception}"
                ) from last_exception

            retries += 1
            sleep_time = ((2 ** retries) - 1) / 2
            logger.warning(
                "Redfish request '%s' on '%s' failed. Retrying in %.1fs.",
                method, path, sleep_time,
            )

    def _get_node_id(self, session, url_base):
        """Get the node ID from the Redfish Systems collection.

        If a node_id is provided in context, use that. Otherwise, discover
        the first member of the Systems collection.
        """
        systems = self._redfish_request(
            session, "GET", REDFISH_SYSTEMS_ENDPOINT, url_base=url_base
        )
        members = systems.get("Members", [])
        if not members:
            raise RuntimeError("No computer systems found in Redfish Systems collection")
        # Get the first system's ID from the odata.id
        system_id = members[0]["@odata.id"].rstrip("/").split("/")[-1]
        return system_id

    def _get_system_power_state(self, session, url_base, node_id):
        """Query the system resource and return the power state."""
        system_path = f"{REDFISH_SYSTEMS_ENDPOINT}/{node_id}"
        system = self._redfish_request(
            session, "GET", system_path, url_base=url_base
        )
        return system.get("PowerState", "Null")

    def _map_power_state(self, redfish_state):
        """Map a Redfish power state to MAAS power state."""
        if not redfish_state:
            redfish_state = "Null"
        state_lower = redfish_state.lower()
        return POWER_STATE_MAP.get(state_lower, "unknown")

    def _wait_for_status(self, session, url_base, node_id, desired_maas_state, wait_times=(4, 8, 16, 32)):
        """Wait for the system to reach the desired power state."""
        for wait_time in wait_times:
            raw_state = self._get_system_power_state(session, url_base, node_id)
            current_state = self._map_power_state(raw_state)
            if current_state == desired_maas_state:
                return True
            logger.debug(
                "Waiting for node %s to reach state '%s'. Current: '%s'.",
                node_id, desired_maas_state, current_state,
            )
            time.sleep(wait_time)

        raise RuntimeError(
            f"Node '{node_id}' did not transition to state '{desired_maas_state}'."
        )

    def _power(self, session, url_base, node_id, reset_type):
        """Issue a power change command via Redfish Reset action."""
        endpoint = REDFISH_POWER_CONTROL_ENDPOINT % node_id
        self._redfish_request(
            session, "POST", endpoint,
            body={"ResetType": reset_type},
            url_base=url_base,
        )

    def _set_pxe_boot(self, session, url_base, node_id):
        """Set the machine to PXE boot once (matches original driver behavior)."""
        endpoint = f"{REDFISH_SYSTEMS_ENDPOINT}/{node_id}"
        body = {
            "Boot": {
                "BootSourceOverrideEnabled": BOOT_SOURCE_OVERRIDE_ENABLED,
                "BootSourceOverrideTarget": BOOT_SOURCE_PXE,
            }
        }
        try:
            self._redfish_request(session, "PATCH", endpoint, body=body, url_base=url_base)
        except Exception as e:
            logger.warning("Failed to set PXE boot for node %s: %s", node_id, e)

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Maps Redfish power states to MAAS power states:
        - Off, PoweringOn -> off
        - On, Paused, PoweringOff -> on
        - Transitional states (Reset, Unknown, Null) are retried with backoff.

        Returns:
            str: One of 'on', 'off', 'unknown', or 'error'.
        """
        session = self._make_session(context)
        url_base = self._get_url(context)
        node_id = context.get("node_id")
        if not node_id:
            node_id = self._get_node_id(session, url_base)

        # Handle transitional states with retries
        for retry in range(MAX_STATUS_REQUEST_RETRIES):
            raw_state = self._get_system_power_state(session, url_base, node_id)
            if not raw_state:
                raw_state = "Null"
            state_lower = raw_state.lower()

            if state_lower in ("reset", "unknown", "null"):
                # Transitional state - retry with exponential backoff
                if retry == MAX_STATUS_REQUEST_RETRIES - 1:
                    logger.error(
                        "Redfish node %s still in '%s' state after all retries. Giving up.",
                        node_id, raw_state,
                    )
                    return "error"
                sleep_time = ((2 ** retry) - 1) / 2
                logger.warning(
                    "Redfish node %s in transitional state '%s'. Retrying in %.1fs.",
                    node_id, raw_state, sleep_time,
                )
                time.sleep(sleep_time)
                continue

            return self._map_power_state(raw_state)

        return "error"

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system.

        If the system is already on, power it off first, then set PXE boot
        and power on (matching the MAAS provisioning workflow).
        """
        session = self._make_session(context)
        url_base = self._get_url(context)
        node_id = context.get("node_id")
        if not node_id:
            node_id = self._get_node_id(session, url_base)

        # Check current state; if on, power off first (for PXE boot cycle)
        raw_state = self._get_system_power_state(session, url_base, node_id)
        current = self._map_power_state(raw_state)
        if current == "on":
            self._power(session, url_base, node_id, POWER_CHANGE_OFF)
            self._wait_for_status(session, url_base, node_id, "off")

        # Set PXE boot (original behavior)
        self._set_pxe_boot(session, url_base, node_id)

        # Power on the machine
        self._power(session, url_base, node_id, POWER_CHANGE_ON)
        self._wait_for_status(session, url_base, node_id, "on")

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system.

        Only powers off if the system is not already off.
        """
        session = self._make_session(context)
        url_base = self._get_url(context)
        node_id = context.get("node_id")
        if not node_id:
            node_id = self._get_node_id(session, url_base)

        raw_state = self._get_system_power_state(session, url_base, node_id)
        current = self._map_power_state(raw_state)
        if current != "off":
            self._power(session, url_base, node_id, POWER_CHANGE_OFF)
            self._wait_for_status(session, url_base, node_id, "off")

        # Set PXE boot (original behavior, even when powering off)
        self._set_pxe_boot(session, url_base, node_id)

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (force restart)."""
        session = self._make_session(context)
        url_base = self._get_url(context)
        node_id = context.get("node_id")
        if not node_id:
            node_id = self._get_node_id(session, url_base)

        self._power(session, url_base, node_id, POWER_CHANGE_CYCLE)

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system (graceful restart)."""
        session = self._make_session(context)
        url_base = self._get_url(context)
        node_id = context.get("node_id")
        if not node_id:
            node_id = self._get_node_id(session, url_base)

        self._power(session, url_base, node_id, POWER_CHANGE_RESET)

    def set_boot_order(self, system_id: str, context: dict, order: list) -> None:
        """Set boot order is not supported by the Redfish driver."""
        raise NotImplementedError("set_boot_order is not supported by the Redfish driver")
