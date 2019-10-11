# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fence CDU Power Driver."""

__all__ = []

import re
from time import sleep

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerDriver, PowerError
from provisioningserver.utils import shell
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
    get_env_with_locale,
)


class FenceCDUPowerDriver(PowerDriver):

    name = "fence_cdu"
    chassis = True
    description = "Sentry Switch CDU"
    settings = [
        make_setting_field("power_address", "Power address", required=True),
        make_setting_field(
            "power_id", "Power ID", scope=SETTING_SCOPE.NODE, required=True
        ),
        make_setting_field("power_user", "Power user"),
        make_setting_field(
            "power_pass", "Power password", field_type="password"
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")
    queryable = False

    def detect_missing_packages(self):
        if not shell.has_command_available("fence_cdu"):
            return ["fence-agents"]
        return []

    def _issue_fence_cdu_command(
        self,
        command,
        power_address=None,
        power_id=None,
        power_user=None,
        power_pass=None,
        **extra
    ):
        """Issue fence_cdu command for the given power change."""
        try:
            stdout = call_and_check(
                [
                    "fence_cdu",
                    "-a",
                    power_address,
                    "-n",
                    power_id,
                    "-l",
                    power_user,
                    "-p",
                    power_pass,
                    "-o",
                    command,
                ],
                env=get_env_with_locale(),
            )
        except ExternalProcessError as e:
            # XXX 2016-01-08 newell-jensen, bug=1532310:
            # fence-agents fence_action method returns an exit code
            # of 2, by default, for querying power status while machine
            # is OFF.
            if e.returncode == 2 and command == "status":
                return "Status: OFF\n"
            else:
                raise PowerError(
                    "Fence CDU failed issuing command %s for Power ID %s: %s"
                    % (command, power_id, e.output_as_unicode)
                )
        else:
            return stdout.decode("utf-8")

    def power_on(self, system_id, context):
        """Power ON Fence CDU power_id."""
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
            sleep(1)
            if self.power_query(system_id, context) != "off":
                raise PowerError(
                    "Fence CDU unable to power off Power ID %s."
                    % context["power_id"]
                )
        self._issue_fence_cdu_command("on", **context)

    def power_off(self, system_id, context):
        """Power OFF Fence CDU power_id."""
        self._issue_fence_cdu_command("off", **context)

    def power_query(self, system_id, context):
        """Power QUERY Fence CDU power_id."""
        re_status = re.compile(
            r"Status: \s* \b(ON|OFF)\b", re.VERBOSE | re.IGNORECASE
        )
        query_output = self._issue_fence_cdu_command("status", **context)
        # Power query output is `Status: OFF\n` or `Status: ON\n`
        match = re_status.match(query_output)
        if match is None:
            raise PowerError(
                "Fence CDU obtained unexpected response to query of "
                "Power ID %s: %r" % (context["power_id"], query_output)
            )
        else:
            return match.group(1).lower()
