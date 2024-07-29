# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DLI Power Driver."""


import re
from time import sleep

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerDriver,
    PowerError,
)
from provisioningserver.utils import shell
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
    get_env_with_locale,
)


class DLIPowerDriver(PowerDriver):
    name = "dli"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "Digital Loggers, Inc. PDU"
    settings = [
        make_setting_field(
            "outlet_id", "Outlet ID", scope=SETTING_SCOPE.NODE, required=True
        ),
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
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        if not shell.has_command_available("wget"):
            return ["wget"]
        return []

    def _set_outlet_state(
        self,
        power_change,
        outlet_id=None,
        power_user=None,
        power_pass=None,
        power_address=None,
        **extra
    ):
        """Power DLI outlet ON/OFF."""
        try:
            url = "http://{}:{}@{}/outlet?{}={}".format(
                power_user,
                power_pass,
                power_address,
                outlet_id,
                power_change,
            )
            # --auth-no-challenge: send Basic HTTP authentication
            # information without first waiting for the server's challenge.
            call_and_check(
                ["wget", "--auth-no-challenge", "-O", "/dev/null", url],
                env=get_env_with_locale(),
            )
        except ExternalProcessError as e:
            raise PowerActionError(
                "Failed to power %s outlet %s: %s"
                % (power_change, outlet_id, e.output_as_unicode)
            )

    def _query_outlet_state(
        self,
        outlet_id=None,
        power_user=None,
        power_pass=None,
        power_address=None,
        **extra
    ):
        """Query DLI outlet power state.

        Sample snippet of query output from DLI:
        ...
        <!--
        function reg() {
        window.open('http://www.digital-loggers.com/reg.html?SN=LPC751740');
        }
        //-->
        </script>
        </head>
        <!-- state=02 lock=00 -->

        <body alink="#0000FF" vlink="#0000FF">
        <FONT FACE="Arial, Helvetica, Sans-Serif">
        ...
        """
        try:
            url = "http://{}:{}@{}/index.htm".format(
                power_user,
                power_pass,
                power_address,
            )
            # --auth-no-challenge: send Basic HTTP authentication
            # information without first waiting for the server's challenge.
            wget_output = call_and_check(
                ["wget", "--auth-no-challenge", "-qO-", url],
                env=get_env_with_locale(),
            )
            wget_output = wget_output.decode("utf-8")
            match = re.search("<!-- state=([0-9a-fA-F]+)", wget_output)
            if match is None:
                raise PowerError(
                    "Unable to extract power state for outlet %s from "
                    "wget output: %s" % (outlet_id, wget_output)
                )
            else:
                state = match.group(1)
                # state is a bitmap of the DLI's oulet states, where bit 0
                # corresponds to oulet 1's power state, bit 1 corresponds to
                # outlet 2's power state, etc., encoded as hexadecimal.
                if (int(state, 16) & (1 << int(outlet_id) - 1)) > 0:
                    return "on"
                else:
                    return "off"
        except ExternalProcessError as e:
            raise PowerActionError(
                "Failed to power query outlet %s: %s"
                % (outlet_id, e.output_as_unicode)
            )

    def power_on(self, system_id, context):
        """Power on DLI outlet."""
        # Power off the outlet if it is currently on
        if self._query_outlet_state(**context) == "on":
            self._set_outlet_state("OFF", **context)
            sleep(1)
            if self._query_outlet_state(**context) != "off":
                raise PowerError(
                    "Unable to power off outlet %s that is already on."
                    % context["outlet_id"]
                )
        self._set_outlet_state("ON", **context)

    def power_off(self, system_id, context):
        """Power off DLI outlet."""
        self._set_outlet_state("OFF", **context)

    def power_query(self, system_id, context):
        """Power query DLI outlet."""
        return self._query_outlet_state(**context)
