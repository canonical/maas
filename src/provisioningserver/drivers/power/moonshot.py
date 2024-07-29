# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Moonshot IPMI Power Driver."""


import re

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerActionError, PowerDriver
from provisioningserver.utils import shell
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
    get_env_with_locale,
)


class MoonshotIPMIPowerDriver(PowerDriver):
    name = "moonshot"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "HP Moonshot - iLO4 (IPMI)"
    settings = [
        make_setting_field(
            "power_address",
            "Power address",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_user", "Power user"),
        make_setting_field(
            "power_pass", "Power password", field_type="password", secret=True
        ),
        make_setting_field(
            "power_hwaddress",
            "Power hardware address",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        if not shell.has_command_available("ipmitool"):
            return ["ipmitool"]
        return []

    def _issue_ipmitool_command(
        self,
        power_change,
        power_address=None,
        power_user=None,
        power_pass=None,
        power_hwaddress=None,
        **extra
    ):
        """Issue ipmitool command for HP Moonshot cartridge."""
        command = (
            "ipmitool",
            "-I",
            "lanplus",
            "-H",
            power_address,
            "-U",
            power_user,
            "-P",
            power_pass,
            "-L",
            "OPERATOR",
        ) + tuple(power_hwaddress.split())
        if power_change == "pxe":
            command += ("chassis", "bootdev", "pxe")
        else:
            command += ("power", power_change)
        try:
            stdout = call_and_check(command, env=get_env_with_locale())
            stdout = stdout.decode("utf-8")
        except ExternalProcessError as e:
            raise PowerActionError(
                "Failed to execute %s for cartridge %s at %s: %s"
                % (
                    command,
                    power_hwaddress,
                    power_address,
                    e.output_as_unicode,
                )
            )
        else:
            # Return output if power query
            if power_change == "status":
                match = re.search(r"\b(on|off)\b$", stdout)
                return stdout if match is None else match.group(0)

    def power_on(self, system_id, context):
        self._issue_ipmitool_command("pxe", **context)
        self._issue_ipmitool_command("on", **context)

    def power_off(self, system_id, context):
        self._issue_ipmitool_command("off", **context)

    def power_query(self, system_id, context):
        return self._issue_ipmitool_command("status", **context)
