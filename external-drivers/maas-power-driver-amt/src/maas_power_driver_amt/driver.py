# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Intel AMT power driver implementation using amtterm, wsmancli."""

import logging
import os
import re
import subprocess
import time

logger = logging.getLogger("maas-power-driver-amt")

AMT_ERRORS = {
    "401 Unauthorized": (
        "Incorrect password. Check BMC configuration and try again."
    ),
    "500 Can't connect": (
        "Could not connect to BMC. Check BMC configuration and try again."
    ),
}

AMT_DEFAULT_USER = "admin"
AMT_HTTP_PORT = "16992"
AMT_HTTPS_PORT = "16993"
AMT_DEFAULT_PORT = AMT_HTTP_PORT

# AMT power state values from wsman CIM_PowerManagementService
# 2: On, 3: Sleep-Light, 4: Sleep-Deep, 5: Power Cycle (Off-Soft)
# 6: Off-Hard, 7: Hibernate (Off-Soft), 8: Off-Soft
# 9: Power Cycle (Off-Hard), 10: Master Bus Reset
# 11: Diagnostic Interrupt (NMI), 12: Off-Soft Graceful
# 13: Off-Hard Graceful, 14: Master Bus Reset Graceful
# 15: Power Cycle (Off-Soft Graceful), 16: Power Cycle (Off-Hard Graceful)
WSMAN_STATES_ON = {"2", "3", "4", "5", "7", "9", "10", "14", "15", "16"}
WSMAN_STATES_OFF = {"6", "8", "12", "13"}

# ACPI states for amttool info output
ACPI_STATES_ON = {"S0", "S1", "S2", "S3", "S4"}
ACPI_STATE_OFF = "S5"


def _check_amt_errors(output):
    """Check output for known AMT error patterns."""
    for error_pattern, message in AMT_ERRORS.items():
        if error_pattern in output:
            raise RuntimeError(message)


class AMTPowerDriver:
    """Intel AMT power driver.

    Interfaces with Intel AMT-compatible BMCs using either amttool
    (for AMT version <= 8) or wsmancli (for AMT version > 8).
    """

    def _parse_context(self, context):
        """Parse and validate the context parameters."""
        ip_address = context.get("power_address")
        if not ip_address:
            raise ValueError("Missing 'power_address' in context")

        power_user = context.get("power_user")
        if not power_user:
            power_user = AMT_DEFAULT_USER

        power_pass = context.get("power_pass", "")
        port = context.get("port", AMT_DEFAULT_PORT)

        return ip_address, power_user, power_pass, port

    def _get_protocol(self, port):
        """Determine http or https based on port."""
        if port == AMT_HTTPS_PORT:
            return "https"
        return "http"

    def _run_command(self, cmd, power_pass, stdin=None):
        """Run a subprocess command with AMT_PASSWORD in environment."""
        env = {**os.environ, "AMT_PASSWORD": power_pass}
        logger.debug("Running command: %s", cmd)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.PIPE if stdin else None,
            input=stdin,
            env=env,
        )
        full_output = result.stdout + result.stderr
        _check_amt_errors(full_output)
        if result.returncode != 0:
            raise RuntimeError(
                f"AMT command failed: {full_output.strip()}"
            )
        return result.stdout

    def _detect_amt_tool(self, ip_address, power_user, power_pass, port):
        """Detect whether to use amttool or wsman based on AMT version.

        AMT version > 8 requires wsman; older versions use amttool.
        """
        protocol = self._get_protocol(port)
        endpoint = f"{protocol}://{power_user}:{power_pass}@{ip_address}:{port}"

        cmd = [
            "wsman",
            "--endpoint", endpoint,
            "--noverifypeer",
            "--noverifyhost",
            "identify",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )

        if not result.stdout:
            _check_amt_errors(result.stderr)
            raise RuntimeError(
                f"Unable to retrieve AMT version: {result.stderr.strip()}"
            )

        match = re.search(r"ProductVersion>AMT\s*([0-9]+)", result.stdout)
        if not match:
            raise RuntimeError(
                f"Unable to extract AMT version from wsman output: {result.stdout}"
            )

        version = int(match.group(1))
        return "wsman" if version > 8 else "amttool"

    # --- amttool methods ---

    def _amttool_query_state(self, ip_address, power_pass, port):
        """Query power state via amttool."""
        for attempt in range(10):
            output = self._run_command(
                ["amttool", f"{ip_address}:{port}", "info"],
                power_pass,
            )
            if output:
                break
            time.sleep(1)
        else:
            raise RuntimeError("amttool power querying failed.")

        if "S5" in output:
            return "off"
        for state in ACPI_STATES_ON:
            if state in output:
                return "on"
        raise RuntimeError(f"Got unknown ACPI power state from node: {output}")

    def _amttool_power_on(self, ip_address, power_pass, port):
        """Power on via amttool."""
        for _ in range(10):
            self._run_command(
                ["amttool", f"{ip_address}:{port}", "powerup", "pxe"],
                power_pass,
                stdin="yes\n",
            )
            if self._amttool_query_state(ip_address, power_pass, port) == "on":
                return
            time.sleep(1)
        raise RuntimeError("Machine is not powering on. Giving up.")

    def _amttool_power_off(self, ip_address, power_pass, port):
        """Power off via amttool."""
        for _ in range(10):
            if self._amttool_query_state(ip_address, power_pass, port) == "off":
                return
            self._run_command(
                ["amttool", f"{ip_address}:{port}", "powerdown"],
                power_pass,
                stdin="yes\n",
            )
            time.sleep(1)
        raise RuntimeError("Machine is not powering off. Giving up.")

    def _amttool_restart(self, ip_address, power_pass, port):
        """Restart via amttool."""
        self._run_command(
            ["amttool", f"{ip_address}:{port}", "power-cycle", "pxe"],
            power_pass,
            stdin="yes\n",
        )

    # --- wsman methods ---

    def _wsman_query_state(self, ip_address, power_user, power_pass, port):
        """Query power state via wsman."""
        protocol = self._get_protocol(port)
        endpoint = f"{protocol}://{power_user}:{power_pass}@{ip_address}:{port}"

        wsman_query_uri = (
            "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
            "CIM_AssociatedPowerManagementService"
        )

        for _ in range(10):
            cmd = [
                "wsman",
                "--endpoint", endpoint,
                "--noverifypeer",
                "--noverifyhost",
                "--optimize",
                "--encoding", "utf-8",
                "enumerate", wsman_query_uri,
            ]
            output = self._run_command(cmd, power_pass)
            if output:
                break
            time.sleep(1)
        else:
            raise RuntimeError("wsman power querying failed.")

        # Extract PowerState from XML output
        match = re.search(r"<PowerState>(\d+)</PowerState>", output)
        if not match:
            raise RuntimeError(
                f"Could not parse PowerState from wsman output: {output}"
            )
        state = match.group(1)

        if state in WSMAN_STATES_ON:
            return "on"
        elif state in WSMAN_STATES_OFF:
            return "off"
        raise RuntimeError(f"Got unknown wsman power state: {state}")

    def _wsman_power_action(self, ip_address, power_user, power_pass, port, action):
        """Issue a power action via wsman.

        action: 'on', 'off', or 'restart'
        """
        protocol = self._get_protocol(port)
        endpoint = f"{protocol}://{power_user}:{power_pass}@{ip_address}:{port}"

        wsman_power_uri = (
            "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
            "CIM_PowerManagementService?SystemCreationClassName="
            '"CIM_ComputerSystem"&SystemName="Intel(r) AMT"'
            '&CreationClassName="CIM_PowerManagementService"&Name='
            '"Intel(r) AMT Power Management Service"'
        )

        # Map action to CIM PowerState value
        state_map = {"on": "2", "off": "8", "restart": "10"}
        power_state = state_map.get(action)
        if not power_state:
            raise ValueError(f"Unknown wsman power action: {action}")

        xml_input = (
            '<?xml version="1.0"?>\n'
            '<p:RequestPowerStateChange_INPUT '
            'xmlns:p="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/'
            '2/CIM_PowerManagementService">\n'
            f'  <p:PowerState>{power_state}</p:PowerState>\n'
            '</p:RequestPowerStateChange_INPUT>'
        )

        cmd = [
            "wsman",
            "--endpoint", endpoint,
            "--noverifypeer",
            "--noverifyhost",
            "--input", "-",
            "invoke",
            "--method", "RequestPowerStateChange",
            wsman_power_uri,
        ]

        self._run_command(cmd, power_pass, stdin=xml_input)

    def _wsman_power_on(self, ip_address, power_user, power_pass, port, restart=False):
        """Power on via wsman."""
        action = "restart" if restart else "on"
        self._wsman_power_action(ip_address, power_user, power_pass, port, action)

        for _ in range(10):
            if self._wsman_query_state(ip_address, power_user, power_pass, port) == "on":
                return
            time.sleep(1)
        raise RuntimeError("Machine is not powering on. Giving up.")

    def _wsman_power_off(self, ip_address, power_user, power_pass, port):
        """Power off via wsman."""
        self._wsman_power_action(ip_address, power_user, power_pass, port, "off")

        for _ in range(10):
            if self._wsman_query_state(ip_address, power_user, power_pass, port) == "off":
                return
            time.sleep(1)
        raise RuntimeError("Machine is not powering off. Giving up.")

    # --- Public interface ---

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Auto-detects whether to use amttool or wsman based on AMT version.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        ip_address, power_user, power_pass, port = self._parse_context(context)
        amt_tool = self._detect_amt_tool(ip_address, power_user, power_pass, port)

        if amt_tool == "amttool":
            return self._amttool_query_state(ip_address, power_pass, port)
        else:
            return self._wsman_query_state(ip_address, power_user, power_pass, port)

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system.

        If the system is already on, performs a restart instead.
        """
        ip_address, power_user, power_pass, port = self._parse_context(context)
        amt_tool = self._detect_amt_tool(ip_address, power_user, power_pass, port)

        if amt_tool == "amttool":
            if self._amttool_query_state(ip_address, power_pass, port) == "on":
                self._amttool_restart(ip_address, power_pass, port)
            else:
                self._amttool_power_on(ip_address, power_pass, port)
        else:
            if self._wsman_query_state(ip_address, power_user, power_pass, port) == "on":
                self._wsman_power_on(ip_address, power_user, power_pass, port, restart=True)
            else:
                self._wsman_power_on(ip_address, power_user, power_pass, port)

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system."""
        ip_address, power_user, power_pass, port = self._parse_context(context)
        amt_tool = self._detect_amt_tool(ip_address, power_user, power_pass, port)

        if amt_tool == "amttool":
            if self._amttool_query_state(ip_address, power_pass, port) != "off":
                self._amttool_power_off(ip_address, power_pass, port)
        else:
            if self._wsman_query_state(ip_address, power_user, power_pass, port) != "off":
                self._wsman_power_off(ip_address, power_user, power_pass, port)

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on)."""
        ip_address, power_user, power_pass, port = self._parse_context(context)
        amt_tool = self._detect_amt_tool(ip_address, power_user, power_pass, port)

        if amt_tool == "amttool":
            self._amttool_restart(ip_address, power_pass, port)
        else:
            self._wsman_power_on(ip_address, power_user, power_pass, port, restart=True)

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system."""
        ip_address, power_user, power_pass, port = self._parse_context(context)
        amt_tool = self._detect_amt_tool(ip_address, power_user, power_pass, port)

        if amt_tool == "amttool":
            self._amttool_restart(ip_address, power_pass, port)
        else:
            self._wsman_power_action(ip_address, power_user, power_pass, port, "restart")

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set boot order (not implemented for AMT).

        The monorepo AMT driver supports PXE boot via _set_pxe_boot using
        wsman XML, but this is deferred for the external driver.
        """
        logger.warning("set_boot_order is not supported by the AMT driver")
