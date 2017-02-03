# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Virsh pod driver."""

__all__ = [
    'probe_virsh_and_enlist',
    'VirshPodDriver',
    ]

from tempfile import NamedTemporaryFile

from lxml import etree
import pexpect
from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    PodDriver,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.utils import (
    commission_node,
    create_node,
)
from provisioningserver.utils import (
    shell,
    typed,
)
from provisioningserver.utils.shell import select_c_utf8_locale
from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("drivers.pod.virsh")


XPATH_ARCH = "/domain/os/type/@arch"
XPATH_BOOT = "/domain/os/boot"
XPATH_OS = "/domain/os"


# Virsh stores the architecture with a different
# label then MAAS. This maps virsh architecture to
# MAAS architecture.
ARCH_FIX = {
    'x86_64': 'amd64/generic',
    'ppc64': 'ppc64el/generic',
    'ppc64le': 'ppc64el/generic',
    'i686': 'i386/generic',
    }


REQUIRED_PACKAGES = [["virsh", "libvirt-bin"],
                     ["virt-login-shell", "libvirt-bin"]]


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
            None, timeout=timeout, maxread=maxread,
            env=select_c_utf8_locale())
        self.name = '<virssh>'
        if dom_prefix is None:
            self.dom_prefix = ''
        else:
            self.dom_prefix = dom_prefix
        # Store a mapping of { machine_name: xml }.
        self.xml = {}

    def _execute(self, poweraddr):
        """Spawns the pexpect command."""
        cmd = 'virsh --connect %s' % poweraddr
        self._spawn(cmd)

    def get_machine_xml(self, machine):
        # Check if we have a cached version of the XML.
        # This is a short-lived object, so we don't need to worry about
        # expiring objects in the cache.
        if machine in self.xml:
            return self.xml[machine]

        # Grab the XML from virsh if we don't have it already.
        output = self.run(['dumpxml', machine]).strip()
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
        cmd = ' '.join(args)
        self.sendline(cmd)
        self.prompt()
        result = self.before.decode("utf-8").splitlines()
        return '\n'.join(result[1:])

    def get_column_values(self, data, keys):
        """Return tuple of column value tuples based off keys."""
        data = data.strip().splitlines()
        cols = data[0].split()
        indexes = []
        # Look for column headers matching keys.
        for k in keys:
            try:
                indexes.append(
                    cols.index(k))
            except:
                # key was not found, continue searching.
                continue
        col_values = []
        if len(indexes) > 0:
            # Iterate over data and return column key values.
            # Skip first two header lines.
            for line in data[2:]:
                line_values = []
                for index in indexes:
                    line_values.append(line.split()[index])
                col_values.append(tuple(line_values))
        return tuple(col_values)

    def get_key_value(self, data, key):
        """Return value based off of key."""
        data = data.strip().splitlines()
        for d in data:
            if key == d.split(':')[0].strip():
                return d.split(':')[1].split()[0]

    def list_machines(self):
        """Lists all VMs by name."""
        machines = self.run(['list', '--all', '--name'])
        machines = machines.strip().splitlines()
        return [m for m in machines if m.startswith(self.dom_prefix)]

    def list_pools(self):
        """Lists all pools in the pod."""
        keys = ['Name']
        output = self.run(['pool-list'])
        pools = self.get_column_values(output, keys)
        return [p[0] for p in pools]

    def list_machine_block_devices(self, machine):
        """Lists all devices for VM."""
        keys = ['Device', 'Target']
        output = self.run(['domblklist', machine, '--details'])
        devices = self.get_column_values(output, keys)
        return [d[1] for d in devices if d[0] == 'disk']

    def get_machine_state(self, machine):
        """Gets the VM state."""
        state = self.run(['domstate', machine]).strip()
        if state.startswith('error:'):
            return None
        return state

    def list_machine_mac_addresses(self, machine):
        """Gets list of mac addressess assigned to the VM."""
        output = self.run(['domiflist', machine]).strip()
        if output.startswith("error:"):
            maaslog.error("%s: Failed to get node MAC addresses", machine)
            return None
        # Skip first two header lines.
        output = output.splitlines()[2:]
        # Only return the last item of the line, as it is ensured that the
        # last item is the MAC Address.
        return [line.split()[-1] for line in output]

    def get_pod_cpu_count(self):
        """Gets number of CPUs in the pod."""
        output = self.run(['nodeinfo']).strip()
        if output is None:
            maaslog.error("Failed to get pod CPU count")
            return None
        return int(self.get_key_value(output, "CPU(s)"))

    def get_machine_cpu_count(self, machine):
        """Gets the VM CPU count."""
        output = self.run(['dominfo', machine]).strip()
        if output is None:
            maaslog.error("%s: Failed to get machine CPU count", machine)
            return None
        return int(self.get_key_value(output, "CPU(s)"))

    def get_pod_cpu_speed(self):
        """Gets CPU speed (MHz) in the pod."""
        output = self.run(['nodeinfo']).strip()
        if output is None:
            maaslog.error("Failed to get pod CPU speed")
            return None
        return int(self.get_key_value(output, "CPU frequency"))

    def get_pod_memory(self):
        """Gets the total memory of the pod."""
        output = self.run(['nodeinfo']).strip()
        if output is None:
            maaslog.error("Failed to get pod memory")
            return None
        KiB = int(self.get_key_value(output, "Memory size"))
        # Memory in MiB.
        return int(KiB / 1024)

    def get_pod_available_memory(self):
        """Gets the available memory of the pod."""
        output = self.run(['nodememstats']).strip()
        if output is None:
            maaslog.error("Failed to get available pod memory")
            return None
        KiB = int(self.get_key_value(output, "free"))
        # Memory in MiB.
        return int(KiB / 1024)

    def get_machine_memory(self, machine):
        """Gets the VM memory."""
        output = self.run(['dominfo', machine]).strip()
        if output is None:
            maaslog.error("%s: Failed to get machine memory", machine)
            return None
        KiB = int(self.get_key_value(output, "Max memory"))
        # Memory in MiB.
        return int(KiB / 1024)

    def get_pod_local_storage(self):
        """Gets the total local storage for the pod."""
        pools = self.list_pools()
        local_storage = 0
        for pool in pools:
            output = self.run(['pool-info', pool]).strip()
            if output is None:
                maaslog.error("Failed to get pod local storage")
                return None
            local_storage += float(self.get_key_value(
                output, "Capacity"))
        # Local storage in bytes. GiB to bytes.
        return int(local_storage * 2**30)

    def get_pod_available_local_storage(self):
        """Gets the available local storage for the pod."""
        pools = self.list_pools()
        local_storage = 0
        for pool in pools:
            output = self.run(['pool-info', pool]).strip()
            if output is None:
                maaslog.error(
                    "Failed to get available pod local storage")
                return None
            local_storage += float(self.get_key_value(
                output, "Available"))
        # Local storage in bytes. GiB to bytes.
        return int(local_storage * 2**30)

    def get_machine_local_storage(self, machine, device):
        """Gets the VM local storage for device."""
        output = self.run(['domblkinfo', machine, device]).strip()
        if output is None:
            maaslog.error(
                "Failed to get available pod local storage")
            return None
        return int(self.get_key_value(output, "Capacity"))

    def get_pod_arch(self):
        """Gets architecture of the pod."""
        output = self.run(['nodeinfo']).strip()
        if output is None:
            maaslog.error("Failed to get pod architecture")
            return None
        return self.get_key_value(output, "CPU model")

    def get_machine_arch(self, machine):
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

    def get_pod_resources(self):
        """Get the pod resources."""
        discovered_pod = DiscoveredPod(
            architectures=[], cores=0, cpu_speed=0, memory=0, local_storage=0,
            hints=DiscoveredPodHints(
                cores=0, cpu_speed=0, memory=0, local_storage=0))
        discovered_pod.architectures = [self.get_pod_arch()]
        discovered_pod.capabilities = [
            Capabilities.DYNAMIC_LOCAL_STORAGE,
            Capabilities.OVER_COMMIT,
        ]
        discovered_pod.cores = self.get_pod_cpu_count()
        discovered_pod.cpu_speed = self.get_pod_cpu_speed()
        discovered_pod.memory = self.get_pod_memory()
        discovered_pod.local_storage = self.get_pod_local_storage()
        return discovered_pod

    def get_pod_hints(self):
        """Gets the discovered pod hints."""
        discovered_pod_hints = DiscoveredPodHints(
            cores=0, cpu_speed=0, memory=0, local_storage=0)
        discovered_pod_hints.memory = self.get_pod_available_memory()
        discovered_pod_hints.local_storage = (
            self.get_pod_available_local_storage())
        return discovered_pod_hints

    def get_discovered_machine(self, machine):
        """Gets the discovered machine."""
        # Discovered machine.
        discovered_machine = DiscoveredMachine(
            architecture="", cores=0, cpu_speed=0, memory=0,
            interfaces=[], block_devices=[], tags=['virtual'])
        discovered_machine.architecture = self.get_machine_arch(machine)
        discovered_machine.cores = self.get_machine_cpu_count(machine)
        discovered_machine.memory = self.get_machine_memory(machine)
        state = self.get_machine_state(machine)
        discovered_machine.power_state = VM_STATE_TO_POWER_STATE[state]
        discovered_machine.power_parameters = {
            'power_id': machine,
        }

        # Discover block devices.
        block_devices = []
        devices = self.list_machine_block_devices(machine)
        for device in devices:
            # Block device.
            block_devices.append(
                DiscoveredMachineBlockDevice(
                    model=None, serial=None,
                    size=self.get_machine_local_storage(machine, device),
                    id_path="/dev/%s" % device))
        discovered_machine.block_devices = block_devices

        # Discover interfaces.
        interfaces = []
        mac_addresses = self.list_machine_mac_addresses(machine)
        for mac in mac_addresses:
            interfaces.append(
                DiscoveredMachineInterface(
                    mac_address=mac))
        discovered_machine.interfaces = interfaces
        return discovered_machine

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
        if (len(boot_elements) == 2 and
                boot_elements[0].attrib['dev'] == 'network' and
                boot_elements[1].attrib['dev'] == 'hd'):
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
            f.write(b'\n')
            f.flush()
            output = self.run(['define', f.name])
            if output.startswith('error:'):
                maaslog.error("%s: Failed to set network boot order", machine)
                return False
            maaslog.info("%s: Successfully set network boot order", machine)
            return True

    def poweron(self, machine):
        """Poweron a VM."""
        output = self.run(['start', machine]).strip()
        if output.startswith("error:"):
            return False
        return True

    def poweroff(self, machine):
        """Poweroff a VM."""
        output = self.run(['destroy', machine]).strip()
        if output.startswith("error:"):
            return False
        return True


class VirshPodDriver(PodDriver):

    name = 'virsh'
    description = "Virsh (virtual systems)"
    settings = [
        make_setting_field(
            'power_address', "Virsh pod address", required=True),
        make_setting_field(
            'power_pass', "Virsh pod password (optional)",
            required=False, field_type='password'),
        make_setting_field(
            'power_id', "Virsh VM ID", scope=SETTING_SCOPE.NODE,
            required=True),
    ]
    ip_extractor = make_ip_extractor(
        'power_address', IP_EXTRACTOR_PATTERNS.URL)

    def detect_missing_packages(self):
        missing_packages = set()
        for binary, package in REQUIRED_PACKAGES:
            if not shell.has_command_available(binary):
                missing_packages.add(package)
        return list(missing_packages)

    @inlineCallbacks
    def power_control_virsh(
            self, power_address, power_id, power_change,
            power_pass=None, **kwargs):
        """Powers controls a VM using virsh."""

        # Force password to None if blank, as the power control
        # script will send a blank password if one is not set.
        if power_pass == '':
            power_pass = None

        conn = VirshSSH()
        logged_in = yield deferToThread(conn.login, power_address, power_pass)
        if not logged_in:
            raise VirshError('Failed to login to virsh console.')

        state = yield deferToThread(conn.get_machine_state, power_id)
        if state is None:
            raise VirshError('%s: Failed to get power state' % power_id)

        if state == VirshVMState.OFF:
            if power_change == 'on':
                powered_on = yield deferToThread(conn.poweron, power_id)
                if powered_on is False:
                    raise VirshError('%s: Failed to power on VM' % power_id)
        elif state == VirshVMState.ON:
            if power_change == 'off':
                powered_off = yield deferToThread(conn.poweroff, power_id)
                if powered_off is False:
                    raise VirshError('%s: Failed to power off VM' % power_id)

    @inlineCallbacks
    def power_state_virsh(
            self, power_address, power_id, power_pass=None, **kwargs):
        """Return the power state for the VM using virsh."""

        # Force password to None if blank, as the power control
        # script will send a blank password if one is not set.
        if power_pass == '':
            power_pass = None

        conn = VirshSSH()
        logged_in = yield deferToThread(conn.login, power_address, power_pass)
        if not logged_in:
            raise VirshError('Failed to login to virsh console.')

        state = yield deferToThread(conn.get_machine_state, power_id)
        if state is None:
            raise VirshError('Failed to get domain: %s' % power_id)

        try:
            return VM_STATE_TO_POWER_STATE[state]
        except KeyError:
            raise VirshError('Unknown state: %s' % state)

    @asynchronous
    def power_on(self, system_id, context):
        """Power on Virsh node."""
        return self.power_control_virsh(power_change='on', **context)

    @asynchronous
    def power_off(self, system_id, context):
        """Power off Virsh node."""
        return self.power_control_virsh(power_change='off', **context)

    @asynchronous
    def power_query(self, system_id, context):
        """Power query Virsh node."""
        return self.power_state_virsh(**context)

    @inlineCallbacks
    def discover(self, system_id, context):
        """Discover all resources.

        Rertuns a defer to a DiscoveredPod object.
        """
        power_address = context.get('power_address')
        power_pass = context.get('power_pass')
        # Login to Virsh console.
        conn = VirshSSH()
        logged_in = yield deferToThread(conn.login, power_address, power_pass)
        if not logged_in:
            raise VirshError('Failed to login to virsh console.')

        # Discover pod resources.
        discovered_pod = yield conn.get_pod_resources()

        # Discovered pod hints.
        discovered_pod.hints = yield conn.get_pod_hints()
        discovered_pod.hints.cores = discovered_pod.cores
        discovered_pod.hints.cpu_speed = discovered_pod.cpu_speed

        # Discover VMs.
        machines = []
        virtual_machines = yield deferToThread(conn.list_machines)
        for vm in virtual_machines:
            discovered_machine = yield conn.get_discovered_machine(vm)
            discovered_machine.cpu_speed = discovered_pod.cpu_speed
            machines.append(discovered_machine)
        discovered_pod.machines = machines

        # Return the DiscoveredPod
        return discovered_pod

    @inlineCallbacks
    def compose(self, system_id, context, request):
        """Compose machine."""
        raise NotImplementedError

    @inlineCallbacks
    def decompose(self, system_id, context):
        """Decompose machine."""
        raise NotImplementedError


@synchronous
@typed
def probe_virsh_and_enlist(
        user: str, poweraddr: str, password: str=None,
        prefix_filter: str=None, accept_all: bool=False,
        domain: str=None):
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
    logged_in = conn.login(poweraddr, password)
    if not logged_in:
        raise VirshError('Failed to login to virsh console.')

    conn_list = conn.list_machines()
    for machine in conn_list:
        arch = conn.get_machine_arch(machine)
        state = conn.get_machine_state(machine)
        macs = conn.list_machine_mac_addresses(machine)

        params = {
            'power_address': poweraddr,
            'power_id': machine,
        }
        if password is not None:
            params['power_pass'] = password
        system_id = create_node(
            macs, arch, 'virsh', params, domain, machine).wait(30)

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
