# Copyright 2016-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Facebook's Wedge Power Driver."""


from socket import error as SOCKETError

from paramiko import AutoAddPolicy, SSHClient, SSHException

from provisioningserver.drivers import make_ip_extractor, make_setting_field
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerDriver,
    PowerFatalError,
)


class WedgeState:
    OFF = "Microserver power is off"
    ON = "Microserver power is on"


class WedgePowerDriver(PowerDriver):
    name = "wedge"
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = "Facebook's Wedge"
    settings = [
        make_setting_field(
            "power_address",
            "IP address",
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
        # uses pure-python paramiko ssh client - nothing to look for!
        return []

    def run_wedge_command(
        self,
        command,
        power_address=None,
        power_user=None,
        power_pass=None,
        **extra
    ):
        """Run a single command and return unparsed text from stdout."""
        try:
            ssh_client = SSHClient()
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            ssh_client.connect(
                power_address, username=power_user, password=power_pass
            )
            _, stdout, _ = ssh_client.exec_command(command)
            output = stdout.read().decode("utf-8").strip()
        except (SSHException, EOFError, SOCKETError) as e:
            raise PowerConnError(
                "Could not make SSH connection to Wedge for "
                "%s on %s - %s" % (power_user, power_address, e)
            )
        finally:
            ssh_client.close()

        return output

    def power_on(self, system_id, context):
        """Power on Wedge."""
        try:
            self.run_wedge_command(
                "/usr/local/bin/wedge_power.sh on", **context
            )
        except PowerConnError:
            raise PowerActionError("Wedge Power Driver unable to power on")

    def power_off(self, system_id, context):
        """Power off Wedge."""
        try:
            self.run_wedge_command(
                "/usr/local/bin/wedge_power.sh off", **context
            )
        except PowerConnError:
            raise PowerActionError("Wedge Power Driver unable to power off")

    def power_query(self, system_id, context):
        """Power query Wedge."""
        try:
            power_state = self.run_wedge_command(
                "/usr/local/bin/wedge_power.sh status", **context
            )
        except PowerConnError:
            raise PowerActionError("Wedge Power Driver unable to power query")
        else:
            if power_state in WedgeState.OFF:
                return "off"
            elif power_state in WedgeState.ON:
                return "on"
            else:
                raise PowerFatalError(
                    "Wedge Power Driver retrieved unknown power response %s"
                    % power_state
                )

    def power_reset(self, system_id, context):
        """Power reset Wedge."""
        raise NotImplementedError()
