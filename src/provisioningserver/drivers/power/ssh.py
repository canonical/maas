# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""SSH Power Driver.

Issue command to control power through SSH.
"""

__all__ = []

from subprocess import (
    PIPE,
    Popen,
)

from provisioningserver.drivers import (
    make_setting_field,
)
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerDriver,
)
from provisioningserver.utils import shell
from provisioningserver.utils.shell import get_env_with_locale

from provisioningserver.logger import get_maas_logger
from twisted.internet.defer import maybeDeferred

maaslog = get_maas_logger("drivers.power.ssh")

class SSHPowerDriver(PowerDriver):
    """Power control through issuing SSH command."""

    name = 'ssh'
    chassis = True
    description = "Issue Command through SSH"
    settings = [
        make_setting_field(
            'username', "Username", required=True),
        make_setting_field(
            'device_address', "IP for Target Device", required=True),
        make_setting_field(
            'key_path', "Paired key on MaaS server", required=True),
    ]
    ip_extractor = None
    queryable = False

    def detect_missing_packages(self):
        binary, package = ['ssh', 'openssh-client']
        if not shell.has_command_available(binary):
            return [package]
        return []

    @classmethod
    def run_process(cls, command):
        """Run SSH command in subprocess."""
        proc = Popen(
            command.split(), stdout=PIPE, stderr=PIPE,
            env=get_env_with_locale())
        stdout, stderr = proc.communicate()
        stdout = stdout.decode("utf-8")
        stderr = stderr.decode("utf-8")
        if proc.returncode != 0:
            raise PowerActionError(
                "APC Power Driver external process error for command %s: %s: %s"
                % (command, stdout, stderr))

    def on(self, system_id, context):
        """Override `on` as we do not need retry logic."""
        return maybeDeferred(self.power_on, system_id, context)

    def off(self, system_id, context):
        """Override `off` as we do not need retry logic."""
        return maybeDeferred(self.power_off, system_id, context)

    def query(self, system_id, context):
        """Override `query` as we do not need retry logic."""
        return maybeDeferred(self.power_query, system_id, context)

    def power_on(self, system_id, context):
        """Power on machine through ssh."""
        maaslog.info(
            "You need to power on %s manually.", system_id)
        self.run_process('ssh ' + '-o StrictHostKeyChecking=no ' + \
            '-o UserKnownHostsFile=/dev/null ' + '-i ' + context['key_path'] + \
            ' -t ' + context['username'] + '@' + context['device_address'] + \
            ' (sleep 5; sudo reboot) &')

    def power_off(self, system_id, context):
        """Power off machine manually."""
        maaslog.info(
            "You need to power off %s manually.", system_id)

    def power_query(self, system_id, context):
        """Power query machine manually."""
        maaslog.info(
            "You need to check power state of %s manually.", system_id)
        return 'unknown'
