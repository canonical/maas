# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from tempfile import NamedTemporaryFile

from lxml import etree
import pexpect

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.shell import get_env_with_locale
from provisioningserver.utils.twisted import synchronous

maaslog = get_maas_logger("drivers.virsh")

XPATH_ARCH = "/domain/os/type/@arch"
XPATH_BOOT = "/domain/os/boot"
XPATH_OS = "/domain/os"

# Virsh stores the architecture with a different
# label then MAAS. This maps virsh architecture to
# MAAS architecture.
ARCH_FIX = {
    "x86_64": "amd64",
    "ppc64": "ppc64el",
    "ppc64le": "ppc64el",
    "i686": "i386",
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
    """Failure communicating to virsh."""


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
        cmd = "virsh --connect %s" % poweraddr
        self._spawn(cmd)

    def get_machine_xml(self, machine):
        # Check if we have a cached version of the XML.
        # This is a short-lived object, so we don't need to worry about
        # expiring objects in the cache.
        if machine in self.xml:
            return self.xml[machine]

        # Grab the XML from virsh if we don't have it already.
        output = self.run(["dumpxml", machine]).strip()
        if output.startswith("error:"):
            maaslog.error("%s: Failed to get XML for machine", machine)
            return None

        # Cache the XML, since we'll need it later to reconfigure the VM.
        self.xml[machine] = output
        return output

    def login(self, poweraddr, password=None):
        """Starts connection to virsh."""
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

    def run(self, args):
        cmd = " ".join(args)
        self.sendline(cmd)
        self.prompt()
        result = self.before.decode("utf-8").splitlines()
        return "\n".join(result[1:])

    def list(self):
        """Lists all VMs by name."""
        machines = self.run(["list", "--all", "--name"])
        machines = machines.strip().splitlines()
        return [m for m in machines if m.startswith(self.dom_prefix)]

    def get_state(self, machine):
        """Gets the VM state."""
        state = self.run(["domstate", machine])
        state = state.strip()
        if state.startswith("error:"):
            return None
        return state

    def get_mac_addresses(self, machine):
        """Gets list of mac addressess assigned to the VM."""
        output = self.run(["domiflist", machine]).strip()
        if output.startswith("error:"):
            maaslog.error("%s: Failed to get node MAC addresses", machine)
            return None
        output = output.splitlines()[2:]
        # Only return the last item of the line, as it is ensured that the
        # last item is the MAC Address.
        return [line.split()[-1] for line in output]

    def get_arch(self, machine):
        """Gets the VM architecture."""
        output = self.get_machine_xml(machine)
        if output is None:
            maaslog.error("%s: Failed to get VM architecture", machine)
            return None

        doc = etree.XML(output)
        evaluator = etree.XPathEvaluator(doc)
        arch = evaluator(XPATH_ARCH)[0]

        # Fix architectures that need to be referenced by a different
        # name, that MAAS understands.
        return ARCH_FIX.get(arch, arch)

    def configure_pxe_boot(self, machine):
        """Given the specified machine, reads the XML dump and determines
        if the boot order needs to be changed. The boot order needs to be
        changed if it isn't (network, hd), and will be changed to that if
        it is found to be set to anything else.
        """
        xml = self.get_machine_xml(machine)
        if xml is None:
            return False
        doc = etree.XML(xml)
        evaluator = etree.XPathEvaluator(doc)

        # Remove any existing <boot/> elements under <os/>.
        boot_elements = evaluator(XPATH_BOOT)

        # Skip this if the boot order is already set up how we want it to be.
        if (
            len(boot_elements) == 2
            and boot_elements[0].attrib["dev"] == "network"
            and boot_elements[1].attrib["dev"] == "hd"
        ):
            return True

        for element in boot_elements:
            element.getparent().remove(element)

        # Grab the <os/> element and put the <boot/> element we want in.
        os = evaluator(XPATH_OS)[0]
        os.append(etree.XML("<boot dev='network'/>"))
        os.append(etree.XML("<boot dev='hd'/>"))

        # Rewrite the XML in a temporary file to use with 'virsh define'.
        with NamedTemporaryFile() as f:
            f.write(etree.tostring(doc))
            f.write(b"\n")
            f.flush()
            output = self.run(["define", f.name])
            if output.startswith("error:"):
                maaslog.error("%s: Failed to set network boot order", machine)
                return False
            maaslog.info("%s: Successfully set network boot order", machine)
            return True

    def poweron(self, machine):
        """Poweron a VM."""
        output = self.run(["start", machine]).strip()
        if output.startswith("error:"):
            return False
        return True

    def poweroff(self, machine):
        """Poweroff a VM."""
        output = self.run(["destroy", machine]).strip()
        if output.startswith("error:"):
            return False
        return True


@synchronous
def probe_virsh_and_enlist(
    user: str,
    poweraddr: str,
    password: str = None,
    prefix_filter: str = None,
    accept_all: bool = False,
    domain: str = None,
):
    """Extracts all of the VMs from virsh and enlists them
    into MAAS.

    :param user: user for the nodes.
    :param poweraddr: virsh connection string.
    :param password: password connection string.
    :param prefix_filter: only enlist nodes that have the prefix.
    :param accept_all: if True, commission enlisted nodes.
    :param domain: The domain for the node to join.
    """
    conn = VirshSSH(dom_prefix=prefix_filter)
    if not conn.login(poweraddr, password):
        raise VirshError("Failed to login to virsh console.")

    for machine in conn.list():
        arch = conn.get_arch(machine)
        state = conn.get_state(machine)
        macs = conn.get_mac_addresses(machine)

        params = {"power_address": poweraddr, "power_id": machine}
        if password is not None:
            params["power_pass"] = password
        system_id = create_node(
            macs, arch, "virsh", params, domain, machine
        ).wait(30)

        # If the system_id is None an error occured when creating the machine.
        # Most likely the error is the node already exists.
        if system_id is None:
            continue

        # Force the machine off, as MAAS will control the machine
        # and it needs to be in a known state of off.
        if state == VirshVMState.ON:
            conn.poweroff(machine)

        conn.configure_pxe_boot(machine)

        if accept_all:
            commission_node(system_id, user).wait(30)

    conn.logout()


def power_control_virsh(poweraddr, machine, power_change, password=None):
    """Powers controls a VM using virsh."""

    # Force password to None if blank, as the power control
    # script will send a blank password if one is not set.
    if password == "":
        password = None

    conn = VirshSSH()
    if not conn.login(poweraddr, password):
        raise VirshError("Failed to login to virsh console.")

    state = conn.get_state(machine)
    if state is None:
        raise VirshError("%s: Failed to get power state" % machine)

    if state == VirshVMState.OFF:
        if power_change == "on":
            if conn.poweron(machine) is False:
                raise VirshError("%s: Failed to power on VM" % machine)
    elif state == VirshVMState.ON:
        if power_change == "off":
            if conn.poweroff(machine) is False:
                raise VirshError("%s: Failed to power off VM" % machine)


def power_state_virsh(poweraddr, machine, password=None):
    """Return the power state for the VM using virsh."""

    # Force password to None if blank, as the power control
    # script will send a blank password if one is not set.
    if password == "":
        password = None

    conn = VirshSSH()
    if not conn.login(poweraddr, password):
        raise VirshError("Failed to login to virsh console.")

    state = conn.get_state(machine)
    if state is None:
        raise VirshError("Failed to get domain: %s" % machine)

    try:
        return VM_STATE_TO_POWER_STATE[state]
    except KeyError:
        raise VirshError("Unknown state: %s" % state)
