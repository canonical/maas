# Copyright 2017-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Virsh power driver."""

from contextlib import suppress
from urllib.parse import urlparse

import pexpect
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerDriver
from provisioningserver.logger import get_maas_logger
from provisioningserver.path import get_path
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.utils import shell
from provisioningserver.utils.shell import get_env_with_locale
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("drivers.power.virsh")

REQUIRED_PACKAGES = [
    ("virsh", "libvirt-clients"),
]


class VirshVMState:
    OFF = "shut off"
    ON = "running"
    NO_STATE = "no state"
    IDLE = "idle"
    PAUSED = "paused"
    IN_SHUTDOWN = "in shutdown"
    CRASHED = "crashed"
    PM_SUSPENDED = "pmsuspended"


VM_STATE_TO_POWER_STATE = {
    VirshVMState.OFF: "off",
    VirshVMState.ON: "on",
    VirshVMState.NO_STATE: "off",
    VirshVMState.IDLE: "off",
    VirshVMState.PAUSED: "off",
    VirshVMState.IN_SHUTDOWN: "on",
    VirshVMState.CRASHED: "off",
    VirshVMState.PM_SUSPENDED: "off",
}


class VirshError(Exception):
    """Failure communicating to virsh."""


class VirshSSH(pexpect.spawn):
    PROMPT = r"virsh \#"
    PROMPT_SSHKEY = "(?i)are you sure you want to continue connecting"
    PROMPT_PASSWORD = "(?i)(?:password)|(?:passphrase for key)"
    # Credential problems
    PROMPT_DENIED = "(?i)permission denied, please try again"
    PROMPT_CLOSED = "(?i)connection closed by remote host"

    PROMPTS = [
        PROMPT_SSHKEY,
        PROMPT_PASSWORD,
        PROMPT,
        PROMPT_DENIED,
        PROMPT_CLOSED,
        pexpect.TIMEOUT,
        pexpect.EOF,
    ]

    I_PROMPT = PROMPTS.index(PROMPT)
    I_PROMPT_SSHKEY = PROMPTS.index(PROMPT_SSHKEY)
    I_PROMPT_PASSWORD = PROMPTS.index(PROMPT_PASSWORD)

    def __init__(self, timeout=30, maxread=2000, dom_prefix=None):
        super().__init__(
            None, timeout=timeout, maxread=maxread, env=get_env_with_locale()
        )
        self.name = "<virssh>"
        if dom_prefix is None:
            self.dom_prefix = ""
        else:
            self.dom_prefix = dom_prefix
        # Store a mapping of { machine_name: xml }.
        self.xml = {}

    def _execute(self, poweraddr):
        """Spawns the pexpect command."""
        self._spawn(f"virsh --connect {poweraddr}")

    def login(self, poweraddr, password=None):
        """Starts connection to virsh."""
        # Extra paramaeters are not allowed as this is a security
        # hole for allowing a user to run executables.
        parsed = urlparse(poweraddr)
        if parsed.query:
            raise VirshError(
                "Supplying extra parameters to the Virsh address"
                " is not supported."
            )

        # Append unverified-ssh command. See,
        # https://bugs.launchpad.net/maas/+bug/1807231
        # for more details.
        poweraddr = (
            poweraddr + "?command=" + get_path("/usr/lib/maas/unverified-ssh")
        )
        self._execute(poweraddr)
        i = self.expect(self.PROMPTS, timeout=self.timeout)
        if i == self.I_PROMPT_SSHKEY:
            # New certificate, lets always accept but if
            # it changes it will fail to login.
            self.sendline("yes")
            i = self.expect(self.PROMPTS)
        if i == self.I_PROMPT_PASSWORD:
            # Requesting password, give it if available.
            if password is None:
                self.close()
                return False
            self.sendline(password)
            i = self.expect(self.PROMPTS)
        if i != self.I_PROMPT:
            # Something bad happened, either disconnect,
            # timeout, wrong password.
            self.close()
            return False
        return True

    def logout(self):
        """Quits the virsh session."""
        self.sendline("quit")
        self.close()

    def prompt(self, timeout=None):
        """Waits for virsh prompt."""
        if timeout is None:
            timeout = self.timeout
        i = self.expect([self.PROMPT, pexpect.TIMEOUT], timeout=timeout)
        if i == 1:
            return False
        return True

    def run(self, args, raise_error=True):
        cmd = " ".join(args)
        self.sendline(cmd)
        self.prompt()
        output = self.before.decode("utf-8").strip()
        # remove the first line since it containes the issued command
        output = "\n".join(output.splitlines()[1:])
        if output.startswith("error:"):
            message = f"Virsh command {args} failed: {output[7:]}"
            maaslog.error(message)
            if raise_error:
                raise VirshError(message)
            return ""  # return empty output if something failed
        return output

    def get_machine_state(self, machine):
        """Gets the VM state."""
        with suppress(VirshError):
            return self._get_machine_state(machine)

    def poweron(self, machine):
        """Poweron a VM."""
        try:
            self.run(["start", machine])
        except VirshError:
            return False
        return True

    def poweroff(self, machine):
        """Poweroff a VM."""
        try:
            self.run(["destroy", machine])
        except VirshError:
            return False
        return True

    @PROMETHEUS_METRICS.failure_counter("maas_virsh_fetch_description_failure")
    def _get_machine_state(self, machine):
        return self.run(["domstate", machine])


class VirshPowerDriver(PowerDriver):
    name = "virsh"
    description = "Virsh (virtual systems)"
    # Virtual machines on the same host share a single BMC (the hypervisor),
    # so the driver must be a chassis for BMC deduplication to work.
    chassis = True
    can_probe = True
    can_set_boot_order = False
    settings = [
        make_setting_field("power_address", "Address", required=True),
        make_setting_field(
            "power_pass",
            "Password (optional)",
            required=False,
            field_type="password",
            secret=True,
        ),
        make_setting_field(
            "power_id", "Virsh VM ID", scope=SETTING_SCOPE.NODE, required=True
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    def detect_missing_packages(self):
        missing_packages = set()
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.add(package)
        return list(missing_packages)

    @inlineCallbacks
    def power_control_virsh(
        self, power_address, power_id, power_change, power_pass=None, **kwargs
    ):
        """Powers controls a VM using virsh."""

        # Force password to None if blank, as the power control
        # script will send a blank password if one is not set.
        if power_pass == "":
            power_pass = None

        conn = VirshSSH()
        logged_in = yield deferToThread(conn.login, power_address, power_pass)
        if not logged_in:
            raise VirshError("Failed to login to virsh console.")

        state = yield deferToThread(conn.get_machine_state, power_id)
        if state is None:
            raise VirshError("%s: Failed to get power state" % power_id)

        if state == VirshVMState.OFF:
            if power_change == "on":
                powered_on = yield deferToThread(conn.poweron, power_id)
                if powered_on is False:
                    raise VirshError("%s: Failed to power on VM" % power_id)
        elif state == VirshVMState.ON:
            if power_change == "off":
                powered_off = yield deferToThread(conn.poweroff, power_id)
                if powered_off is False:
                    raise VirshError("%s: Failed to power off VM" % power_id)

    @inlineCallbacks
    def power_state_virsh(
        self, power_address, power_id, power_pass=None, **kwargs
    ):
        """Return the power state for the VM using virsh."""

        # Force password to None if blank, as the power control
        # script will send a blank password if one is not set.
        if power_pass == "":
            power_pass = None

        conn = VirshSSH()
        logged_in = yield deferToThread(conn.login, power_address, power_pass)
        if not logged_in:
            raise VirshError("Failed to login to virsh console.")

        state = yield deferToThread(conn.get_machine_state, power_id)
        if state is None:
            raise VirshError("Failed to get domain: %s" % power_id)

        try:
            return VM_STATE_TO_POWER_STATE[state]
        except KeyError:
            raise VirshError("Unknown state: %s" % state)  # noqa: B904

    @asynchronous
    def power_on(self, system_id, context):
        """Power on Virsh node."""
        return self.power_control_virsh(power_change="on", **context)

    @asynchronous
    def power_off(self, system_id, context):
        """Power off Virsh node."""
        return self.power_control_virsh(power_change="off", **context)

    @asynchronous
    def power_query(self, system_id, context):
        """Power query Virsh node."""
        return self.power_state_virsh(**context)

    @asynchronous
    def power_reset(self, system_id, context):
        """Power reset Virsh node."""
        raise NotImplementedError()
