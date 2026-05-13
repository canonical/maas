# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""IPMI power driver implementation using freeipmi-tools."""

import logging
import re
import subprocess
import tempfile

logger = logging.getLogger("maas-power-driver-ipmi")

IPMI_CONFIG = """\
Section Chassis_Boot_Flags
        Boot_Flags_Persistent                         No
        Boot_Device                                   PXE
EndSection
"""

IPMI_CONFIG_WITH_BOOT_TYPE = """\
Section Chassis_Boot_Flags
        Boot_Flags_Persistent                         No
        BIOS_Boot_Type                                %s
        Boot_Device                                   PXE
Endsection
"""

IPMI_ERRORS = {
    "username invalid": (
        "Incorrect username. Check BMC configuration and try again."
    ),
    "password invalid": (
        "Incorrect password. Check BMC configuration and try again."
    ),
    "password verification timeout": (
        "Authentication timeout. Check BMC configuration and try again."
    ),
    "k_g invalid": "Incorrect K_g key. Check BMC configuration and try again.",
    "privilege level insufficient": (
        "Access denied while performing power action. "
        "Check BMC configuration and try again."
    ),
    "privilege level cannot be obtained for this user": (
        "Access denied while performing power action. "
        "Check BMC configuration and try again."
    ),
    "authentication type unavailable for attempted privilege level": (
        "Access denied while performing power action: authentication type "
        "unavailable. Check BMC configuration and try again."
    ),
    "cipher suite id unavailable": (
        "Access denied while performing power action: cipher suite "
        "unavailable. Check BMC configuration and try again."
    ),
    "ipmi 2.0 unavailable": (
        "IPMI 2.0 was not discovered on the BMC. "
        "Please try to use IPMI 1.5 instead."
    ),
    "connection timeout": (
        "Connection timed out while performing power action. "
        "Check BMC configuration and connectivity and try again."
    ),
    "session timeout": (
        "The IPMI session has timed out. MAAS performed several retries. "
        "Check BMC configuration and connectivity and try again."
    ),
    "internal IPMI error": (
        "An IPMI error has occurred that FreeIPMI does not know how to "
        "handle. Please try the power action manually, and file a bug if "
        "appropriate."
    ),
    "device not found": (
        "Error locating IPMI device. Check BMC configuration and try again."
    ),
    "driver timeout": (
        "Device communication timeout while performing power action. "
        "MAAS performed several retries. Check BMC configuration and "
        "connectivity and try again."
    ),
    "message timeout": (
        "Device communication timeout while performing power action. "
        "MAAS performed several retries. Check BMC configuration and "
        "connectivity and try again."
    ),
    "BMC busy": (
        "Device busy while performing power action. "
        "MAAS performed several retries. Please wait and try again."
    ),
    "could not find inband device": (
        "An inband device could not be found. "
        "Check BMC configuration and try again."
    ),
}


def _is_power_parameter_set(value):
    """Check if a power parameter has a meaningful value."""
    return value is not None and str(value).strip() != ""


class IPMIPowerDriver:
    """IPMI power driver that interfaces with BMCs via freeipmi-tools.

    Uses ipmipower and ipmi-chassis-config to communicate with
    IPMI-compatible baseboard management controllers.
    """

    def _build_common_args(self, context):
        """Build the common arguments shared between ipmi-chassis-config and ipmipower."""
        common_args = []

        power_driver = context.get("power_driver")
        if _is_power_parameter_set(power_driver):
            common_args.extend(["--driver-type", power_driver])

        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")
        common_args.extend(["-h", power_address])

        power_user = context.get("power_user")
        if _is_power_parameter_set(power_user):
            common_args.extend(["-u", power_user])

        power_pass = context.get("power_pass", "")
        common_args.extend(["-p", power_pass])

        k_g = context.get("k_g")
        if _is_power_parameter_set(k_g):
            common_args.extend(["-k", k_g])

        cipher_suite_id = context.get("cipher_suite_id")
        if _is_power_parameter_set(cipher_suite_id):
            if cipher_suite_id != "17":
                logger.warning("using a non-secure cipher suite id")
            common_args.extend(["-I", cipher_suite_id])

        privilege_level = context.get("privilege_level")
        if _is_power_parameter_set(privilege_level):
            common_args.extend(["-l", privilege_level])
        else:
            # Default to operator level (LP:1889788).
            common_args.extend(["-l", "operator"])

        return common_args

    def _get_workaround_flags(self, context):
        """Get workaround flags, defaulting to opensesspriv."""
        workaround_flags = context.get("workaround_flags")
        if not workaround_flags:
            return ["opensesspriv"]
        return workaround_flags

    def _build_workaround_args(self, workaround_flags):
        """Build workaround arguments for ipmipower/ipmi-chassis-config."""
        if not workaround_flags:
            return []
        args = []
        for flag in workaround_flags:
            args.extend(["-W", flag])
        return args

    def _check_ipmi_errors(self, output):
        """Check output for known IPMI error patterns and raise appropriately."""
        for error_pattern, message in IPMI_ERRORS.items():
            if error_pattern in output:
                raise RuntimeError(message)

    def _run_ipmipower(self, context, power_change, additional_args):
        """Run an ipmipower command and return stdout.

        This is the core method that builds and executes ipmipower commands.
        """
        workaround_flags = self._get_workaround_flags(context)
        common_args = self._build_common_args(context)

        cmd = ["ipmipower"] + self._build_workaround_args(workaround_flags)
        cmd.extend(common_args)
        cmd.extend(additional_args)

        logger.debug("Running ipmipower: %s", cmd)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # ipmipower dumps errors to stdout
        full_output = result.stdout + result.stderr
        self._check_ipmi_errors(full_output)

        if result.returncode != 0:
            raise RuntimeError(
                f"ipmipower failed: {full_output.strip()}"
            )
        return result.stdout.strip()

    def _run_ipmi_chassis_config(self, context):
        """Run ipmi-chassis-config to set PXE boot configuration.

        This is called before powering on to ensure the machine boots to PXE.
        """
        workaround_flags = self._get_workaround_flags(context)
        common_args = self._build_common_args(context)
        power_boot_type = context.get("power_boot_type")

        # Build config content
        if _is_power_parameter_set(power_boot_type):
            config_content = IPMI_CONFIG_WITH_BOOT_TYPE % power_boot_type
        else:
            config_content = IPMI_CONFIG

        # Write config to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cfg", delete=False
        ) as tmp:
            tmp.write(config_content)
            tmp_path = tmp.name

        try:
            cmd = (
                ["ipmi-chassis-config"]
                + self._build_workaround_args(workaround_flags)
                + common_args
                + ["--commit", tmp_path]
            )
            logger.debug("Running ipmi-chassis-config: %s", cmd)
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            full_output = result.stdout + result.stderr
            self._check_ipmi_errors(full_output)
            if result.returncode != 0:
                raise RuntimeError(
                    f"ipmi-chassis-config failed: {full_output.strip()}"
                )
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except OSError:
                pass

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state of the system.

        Returns:
            str: One of 'on', 'off', or 'unknown'.
        """
        try:
            output = self._run_ipmipower(context, "query", ["--stat"])
            # ipmipower --stat output contains ": on" or ": off"
            match = re.search(r":\s*(on|off)", output)
            if match:
                return match.group(1)
            return "unknown"
        except Exception as e:
            logger.error("IPMI query failed: %s", e)
            raise

    def on(self, system_id: str, context: dict) -> None:
        """Power on the system.

        Sets PXE boot via ipmi-chassis-config, then issues a cycle command
        with --on-if-off to power on the machine.
        """
        # Set PXE boot configuration first.
        self._run_ipmi_chassis_config(context)
        # Issue power on command.
        # --cycle --on-if-off ensures the machine powers on and cycles to PXE.
        self._run_ipmipower(
            context, "on", ["--cycle", "--on-if-off"]
        )

    def off(self, system_id: str, context: dict) -> None:
        """Power off the system.

        Supports both hard and soft power off modes via the power_off_mode
        context parameter.
        """
        power_off_mode = context.get("power_off_mode", "hard")
        if power_off_mode == "soft":
            self._run_ipmipower(context, "off", ["--soft"])
        else:
            self._run_ipmipower(context, "off", ["--off"])

    def cycle(self, system_id: str, context: dict) -> None:
        """Cycle power (off then on)."""
        self._run_ipmipower(context, "cycle", ["--cycle"])

    def reset(self, system_id: str, context: dict) -> None:
        """Hard reset the system.

        Performs a cycle operation as a reset equivalent.
        """
        self._run_ipmipower(context, "reset", ["--cycle"])

    def set_boot_order(self, system_id: str, context: dict) -> None:
        """Set the boot order for the system.

        Uses ipmi-chassis-config to set PXE as the boot device.
        """
        self._run_ipmi_chassis_config(context)
