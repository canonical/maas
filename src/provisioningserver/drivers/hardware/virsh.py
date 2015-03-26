# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'probe_virsh_and_enlist',
    ]

from lxml import etree
import pexpect
from provisioningserver.utils import (
    commission_node,
    create_node,
)
from provisioningserver.utils.twisted import synchronous


XPATH_ARCH = "/domain/os/type/@arch"

# Virsh stores the architecture with a different
# label then MAAS. This maps virsh architecture to
# MAAS architecture.
ARCH_FIX = {
    'x86_64': 'amd64',
    'ppc64': 'ppc64el',
    'i686': 'i386',
    }


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
    """Failure communicating to virsh. """


class VirshSSH(pexpect.spawn):

    PROMPT = r"virsh \#"
    PROMPT_SSHKEY = "(?i)are you sure you want to continue connecting"
    PROMPT_PASSWORD = "(?i)(?:password)|(?:passphrase for key)"
    PROMPT_DENIED = "(?i)permission denied"
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
        super(VirshSSH, self).__init__(
            None, timeout=timeout, maxread=maxread)
        self.name = '<virssh>'
        if dom_prefix is None:
            self.dom_prefix = ''
        else:
            self.dom_prefix = dom_prefix

    def _execute(self, poweraddr):
        """Spawns the pexpect command."""
        cmd = 'virsh --connect %s' % poweraddr
        self._spawn(cmd)

    def login(self, poweraddr, password=None):
        """Starts connection to virsh."""
        self._execute(poweraddr)
        i = self.expect(self.PROMPTS, timeout=min(10, self.timeout))
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

    def run(self, args):
        cmd = ' '.join(args)
        self.sendline(cmd)
        self.prompt()
        result = self.before.splitlines()
        return '\n'.join(result[1:])

    def list(self):
        """Lists all virtual machines by name."""
        machines = self.run(['list', '--all', '--name'])
        machines = machines.strip().splitlines()
        return [m for m in machines if m.startswith(self.dom_prefix)]

    def get_state(self, machine):
        """Gets the virtual machine state."""
        state = self.run(['domstate', machine])
        state = state.strip()
        if 'error' in state:
            return None
        return state

    def get_mac_addresses(self, machine):
        """Gets list of mac addressess assigned to the virtual machine."""
        output = self.run(['domiflist', machine]).strip()
        if 'error' in output:
            return None
        output = output.splitlines()[2:]
        # Only return the last item of the line, as it is ensured that the
        # last item is the MAC Address.
        return [line.split()[-1] for line in output]

    def get_arch(self, machine):
        """Gets the virtual machine architecture."""
        output = self.run(['dumpxml', machine]).strip()
        if 'error' in output:
            return None

        doc = etree.XML(output)
        evaluator = etree.XPathEvaluator(doc)
        arch = evaluator(XPATH_ARCH)[0]

        # Fix architectures that need to be referenced by a different
        # name, that MAAS understands.
        return ARCH_FIX.get(arch, arch)

    def poweron(self, machine):
        """Poweron a virtual machine."""
        output = self.run(['start', machine]).strip()
        if 'error' in output:
            return False
        return True

    def poweroff(self, machine):
        """Poweroff a virtual machine."""
        output = self.run(['destroy', machine]).strip()
        if 'error' in output:
            return False
        return True


@synchronous
def probe_virsh_and_enlist(user, poweraddr, password=None,
                           prefix_filter=None, accept_all=False):
    """Extracts all of the virtual machines from virsh and enlists them
    into MAAS.

    :param user: user for the nodes.
    :param poweraddr: virsh connection string.
    :param password: password connection string.
    :param prefix_filter: only enlist nodes that have the prefix.
    :param accept_all: if True, commission enlisted nodes.
    """
    conn = VirshSSH(dom_prefix=prefix_filter)
    if not conn.login(poweraddr, password):
        raise VirshError('Failed to login to virsh console.')

    for machine in conn.list():
        arch = conn.get_arch(machine)
        state = conn.get_state(machine)
        macs = conn.get_mac_addresses(machine)

        # Force the machine off, as MAAS will control the machine
        # and it needs to be in a known state of off.
        if state == VirshVMState.ON:
            conn.poweroff(machine)

        params = {
            'power_address': poweraddr,
            'power_id': machine,
        }
        if password is not None:
            params['power_pass'] = password
        system_id = create_node(macs, arch, 'virsh', params).wait(30)

        if accept_all:
            commission_node(system_id, user).wait(30)

    conn.logout()


def power_control_virsh(poweraddr, machine, power_change, password=None):
    """Powers controls a virtual machine using virsh."""

    # Force password to None if blank, as the power control
    # script will send a blank password if one is not set.
    if password == '':
        password = None

    conn = VirshSSH()
    if not conn.login(poweraddr, password):
        raise VirshError('Failed to login to virsh console.')

    state = conn.get_state(machine)
    if state is None:
        raise VirshError('Failed to get domain: %s' % machine)

    if state == VirshVMState.OFF:
        if power_change == 'on':
            if conn.poweron(machine) is False:
                raise VirshError('Failed to power on domain: %s' % machine)
    elif state == VirshVMState.ON:
        if power_change == 'off':
            if conn.poweroff(machine) is False:
                raise VirshError('Failed to power off domain: %s' % machine)


def power_state_virsh(poweraddr, machine, password=None):
    """Return the power state for the virtual machine using virsh."""

    # Force password to None if blank, as the power control
    # script will send a blank password if one is not set.
    if password == '':
        password = None

    conn = VirshSSH()
    if not conn.login(poweraddr, password):
        raise VirshError('Failed to login to virsh console.')

    state = conn.get_state(machine)
    if state is None:
        raise VirshError('Failed to get domain: %s' % machine)

    try:
        return VM_STATE_TO_POWER_STATE[state]
    except KeyError:
        raise VirshError('Unknown state: %s' % state)
