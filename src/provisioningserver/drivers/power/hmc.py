# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""HMC Power Driver.

Support for managing lpars via the IBM Hardware Management Console (HMC).
This module provides support for interacting with IBM's HMC via SSH.
"""

from socket import error as SOCKETError

from paramiko import AutoAddPolicy, SSHClient, SSHException

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerDriver,
    PowerFatalError,
)


class HMCState:
    OFF = ("Shutting Down", "Not Activated")
    ON = ("Starting", "Running", "Open Firmware")


class HMCPowerDriver(PowerDriver):
    name = "hmc"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "IBM Hardware Management Console (HMC) for PowerPC"
    settings = [
        make_setting_field(
            "power_address",
            "IP for HMC",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_user", "HMC username"),
        make_setting_field(
            "power_pass", "HMC password", field_type="password", secret=True
        ),
        make_setting_field(
            "server_name",
            "HMC Managed System server name",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "lpar",
            "HMC logical partition",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        # uses pure-python paramiko ssh client - nothing to look for!
        return []

    def run_hmc_command(
        self,
        command,
        power_address=None,
        power_user=None,
        power_pass=None,
        **extra,
    ):
        """Run a single command on HMC via SSH and return output."""
        try:
            ssh_client = SSHClient()
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            ssh_client.connect(
                power_address, username=power_user, password=power_pass
            )
            _, stdout, _ = ssh_client.exec_command(command)
            output = stdout.read().decode("utf-8").strip()
        except (SSHException, EOFError, SOCKETError) as e:
            raise PowerConnError(  # noqa: B904
                "Could not make SSH connection to HMC for "
                "%s on %s - %s" % (power_user, power_address, e)
            )
        finally:
            ssh_client.close()

        return output

    def power_on(self, system_id, context):
        """Power on HMC lpar."""
        if self.power_query(system_id, context) in HMCState.ON:
            self.power_off(system_id, context)
        try:
            # Power lpar on
            self.run_hmc_command(
                "chsysstate -r lpar -m %s -o on -n %s --bootstring network-all"
                % (context["server_name"], context["lpar"]),
                **context,
            )
        except PowerConnError as e:
            raise PowerActionError(  # noqa: B904
                "HMC Power Driver unable to power on lpar %s: %s"
                % (context["lpar"], e)
            )

    def power_off(self, system_id, context):
        """Power off HMC lpar."""
        try:
            # Power lpar off
            self.run_hmc_command(
                "chsysstate -r lpar -m %s -o shutdown -n %s --immed"
                % (context["server_name"], context["lpar"]),
                **context,
            )
        except PowerConnError as e:
            raise PowerActionError(  # noqa: B904
                "HMC Power Driver unable to power off lpar %s: %s"
                % (context["lpar"], e)
            )

    def power_query(self, system_id, context):
        """Power query HMC lpar."""
        try:
            # Power query lpar
            power_state = self.run_hmc_command(
                "lssyscfg -m %s -r lpar -F state --filter lpar_names=%s"
                % (context["server_name"], context["lpar"]),
                **context,
            )
        except PowerConnError as e:
            raise PowerActionError(  # noqa: B904
                "HMC Power Driver unable to power query lpar %s: %s"
                % (context["lpar"], e)
            )
        else:
            if power_state in HMCState.OFF:
                return "off"
            elif power_state in HMCState.ON:
                return "on"
            else:
                raise PowerFatalError(
                    "HMC Power Driver retrieved unknown power state %s"
                    " for lpar %s" % (power_state, context["lpar"])
                )

    def power_reset(self, system_id, context):
        """Power reset HMC lpar."""
        raise NotImplementedError()
