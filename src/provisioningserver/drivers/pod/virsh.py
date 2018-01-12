# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Virsh pod driver."""

__all__ = [
    'probe_virsh_and_enlist',
    'VirshPodDriver',
    ]

import string
from tempfile import NamedTemporaryFile
from textwrap import dedent
import uuid

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
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.rpc.utils import (
    commission_node,
    create_node,
)
from provisioningserver.utils import (
    convert_size_to_bytes,
    shell,
    typed,
)
from provisioningserver.utils.shell import get_env_with_locale
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


DOM_TEMPLATE = dedent("""\
    <domain type='{type}'>
      <name>{name}</name>
      <uuid>{uuid}</uuid>
      <memory unit='MiB'>{memory}</memory>
      <vcpu>{cores}</vcpu>
      <os>
        <type arch="{arch}">hvm</type>
      </os>
      <features>
        <acpi/>
        <apic/>
      </features>
      <clock offset="utc"/>
      <on_poweroff>destroy</on_poweroff>
      <on_reboot>restart</on_reboot>
      <on_crash>restart</on_crash>
      <pm>
        <suspend-to-mem enabled='no'/>
        <suspend-to-disk enabled='no'/>
      </pm>
      <devices>
        <emulator>{emulator}</emulator>
        <controller type='pci' index='0' model='pci-root'/>
        <controller type='virtio-serial' index='0'>
          <address type='pci' domain='0x0000'
            bus='0x00' slot='0x05' function='0x0'/>
        </controller>
        <serial type='pty'>
          <target port='0'/>
        </serial>
        <console type='pty'>
          <target type='serial' port='0'/>
        </console>
        <channel type='spicevmc'>
          <target type='virtio' name='com.redhat.spice.0'/>
          <address type='virtio-serial' controller='0' bus='0' port='1'/>
        </channel>
        <graphics type='spice' autoport='yes'>
          <image compression='off'/>
        </graphics>
        <input type='mouse' bus='ps2'/>
        <input type='keyboard' bus='ps2'/>
      </devices>
    </domain>
    """)


# Virsh stores the architecture with a different
# label then MAAS. This maps virsh architecture to
# MAAS architecture.
ARCH_FIX = {
    'x86_64': 'amd64/generic',
    'ppc64': 'ppc64el/generic',
    'ppc64le': 'ppc64el/generic',
    'i686': 'i386/generic',
    }
ARCH_FIX_REVERSE = {
    value: key
    for key, value in ARCH_FIX.items()
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
            env=get_env_with_locale())
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
                return d.split(':')[1].strip()

    def get_key_value_unitless(self, data, key):
        """Return value based off of key with unit (if any) stripped off."""
        value = self.get_key_value(data, key)
        if value:
            return value.split()[0]

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
        return int(self.get_key_value_unitless(output, "CPU frequency"))

    def get_pod_memory(self):
        """Gets the total memory of the pod."""
        output = self.run(['nodeinfo']).strip()
        if output is None:
            maaslog.error("Failed to get pod memory")
            return None
        KiB = int(self.get_key_value_unitless(output, "Memory size"))
        # Memory in MiB.
        return int(KiB / 1024)

    def get_machine_memory(self, machine):
        """Gets the VM memory."""
        output = self.run(['dominfo', machine]).strip()
        if output is None:
            maaslog.error("%s: Failed to get machine memory", machine)
            return None
        KiB = int(self.get_key_value_unitless(output, "Max memory"))
        # Memory in MiB.
        return int(KiB / 1024)

    def get_pod_pool_size_map(self, key):
        """Return the mapping for a size calculation based on key."""
        pools = {}
        for pool in self.list_pools():
            output = self.run(['pool-info', pool]).strip()
            if output is None:
                # Skip if cannot get more information.
                continue
            pools[pool] = convert_size_to_bytes(
                self.get_key_value(output, "Capacity"))
        return pools

    def get_pod_local_storage(self):
        """Gets the total local storage for the pod."""
        pools = self.get_pod_pool_size_map("Capacity")
        if len(pools) == 0:
            maaslog.error("Failed to get pod local storage")
            raise PodInvalidResources(
                "Pod does not have a storage pool defined. "
                "Please add a storage pool.")
        return sum(pools.values())

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
            local_storage += convert_size_to_bytes(
                self.get_key_value(output, "Available"))
        # Local storage in bytes.
        return local_storage

    def get_machine_local_storage(self, machine, device):
        """Gets the VM local storage for device."""
        output = self.run(['domblkinfo', machine, device]).strip()
        if output is None:
            maaslog.error(
                "Failed to get available pod local storage")
            return None
        try:
            return int(self.get_key_value(output, "Capacity"))
        except TypeError:
            return None

    def get_pod_arch(self):
        """Gets architecture of the pod."""
        output = self.run(['nodeinfo']).strip()
        if output is None:
            maaslog.error("Failed to get pod architecture")
            return None
        arch = self.get_key_value(output, "CPU model")
        return ARCH_FIX.get(arch, arch)

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
            Capabilities.COMPOSABLE,
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
        # You can always create a domain up to the size of total cores,
        # memory, and cpu_speed even if that amount is already in use.
        # Not a good idea, but possible.
        discovered_pod_hints.cores = self.get_pod_cpu_count()
        discovered_pod_hints.cpu_speed = self.get_pod_cpu_speed()
        discovered_pod_hints.memory = self.get_pod_memory()
        discovered_pod_hints.local_storage = (
            self.get_pod_available_local_storage())
        return discovered_pod_hints

    def get_discovered_machine(self, machine, request=None):
        """Gets the discovered machine."""
        # Discovered machine.
        discovered_machine = DiscoveredMachine(
            architecture="", cores=0, cpu_speed=0, memory=0,
            interfaces=[], block_devices=[], tags=['virtual'])
        discovered_machine.hostname = machine
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
        for idx, device in enumerate(devices):
            # Block device.
            # When request is provided map the tags from the request block
            # devices to the discovered block devices. This ensures that
            # composed machine has the requested tags on the block device.
            tags = []
            if request is not None:
                tags = request.block_devices[idx].tags
            size = self.get_machine_local_storage(machine, device)
            if size is None:
                # Bug lp:1690144 - When a domain has a block device where its
                # storage path is no longer available. The domain cannot be
                # started when the storage path is missing, so we don't add it
                # to MAAS.
                maaslog.error(
                    "Unable to discover machine '%s' in virsh pod: storage "
                    "device '%s' is missing its storage backing." % (
                        machine, device))
                return None
            block_devices.append(
                DiscoveredMachineBlockDevice(
                    model=None, serial=None, size=size,
                    id_path="/dev/%s" % device, tags=tags))
        discovered_machine.block_devices = block_devices

        # Discover interfaces.
        interfaces = []
        mac_addresses = self.list_machine_mac_addresses(machine)
        boot = True
        for mac in mac_addresses:
            interfaces.append(
                DiscoveredMachineInterface(
                    mac_address=mac, boot=boot))
            boot = False
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

    def get_usable_pool(self, size):
        """Return the pool that as enough space for `size`."""
        pools = self.get_pod_pool_size_map("Available")
        for pool, available in pools.items():
            if size <= available:
                return pool
        return None

    def create_local_volume(self, size):
        """Create a local volume with `size`."""
        usable_pool = self.get_usable_pool(size)
        if usable_pool is None:
            return None
        volume = str(uuid.uuid4())
        self.run([
            'vol-create-as', usable_pool, volume, str(size),
            '--allocation', '0', '--format', 'raw'])
        return usable_pool, volume

    def delete_local_volume(self, pool, volume):
        """Delete a local volume from `pool` with `volume`."""
        self.run(['vol-delete', volume, '--pool', pool])

    def get_volume_path(self, pool, volume):
        """Return the path to the file from `pool` and `volume`."""
        output = self.run(['vol-path', volume, '--pool', pool])
        return output.strip()

    def attach_local_volume(self, domain, pool, volume, device):
        """Attach `volume` in `pool` to `domain` as `device`."""
        vol_path = self.get_volume_path(pool, volume)
        self.run([
            'attach-disk', domain, vol_path, device,
            '--targetbus', 'virtio', '--sourcetype', 'file', '--config'])

    def get_network_list(self):
        """Return the list of available networks."""
        output = self.run(['net-list', '--name'])
        return output.strip().splitlines()

    def get_best_network(self):
        """Return the best possible network."""
        networks = self.get_network_list()
        if 'maas' in networks:
            return 'maas'
        elif 'default' in networks:
            return 'default'
        elif not networks:
            raise PodInvalidResources(
                "Pod does not have a network defined. "
                "Please add a 'default' or 'maas' network.")

        return networks[0]

    def attach_interface(self, domain, network):
        """Attach new network interface on `domain` to `network`."""
        self.run([
            'attach-interface', domain, 'network', network,
            '--model', 'virtio', '--config'])

    def get_domain_capabilities(self):
        """Return the domain capabilities.

        Determines the type and emulator of the domain to use.
        """
        try:
            # Test for KVM support first.
            xml = self.run(['domcapabilities', '--virttype', 'kvm'])
            emulator_type = 'kvm'
        except Exception:
            # Fallback to qemu support. Fail if qemu not supported.
            xml = self.run(['domcapabilities', '--virttype', 'qemu'])
            emulator_type = 'qemu'

        # XXX newell 2017-05-18 bug=1690781
        # Check to see if the XML output was an error.
        # See bug for details about why and how this can occur.
        if xml.startswith('error'):
            raise VirshError(
                "`virsh domcapabilities --virttype %s` errored.  Please "
                "verify that package qemu-kvm is installed and restart "
                "libvirt-bin service." % emulator_type)

        doc = etree.XML(xml)
        evaluator = etree.XPathEvaluator(doc)
        emulator = evaluator('/domainCapabilities/path')[0].text
        return {
            'type': emulator_type,
            'emulator': emulator,
        }

    def cleanup_disks(self, pool_vols):
        """Delete all volumes."""
        for pool, volume in pool_vols:
            try:
                self.delete_local_volume(pool, volume)
            except Exception:
                # Ignore any exception trying to cleanup.
                pass

    def get_block_name_from_idx(self, idx):
        """Calculate a block name based on the `idx`.

        Drive#  Name
        0	    vda
        25	    vdz
        26	    vdaa
        27	    vdab
        51	    vdaz
        52	    vdba
        53	    vdbb
        701	    vdzz
        702	    vdaaa
        703	    vdaab
        18277   vdzzz
        """
        name = ""
        while idx >= 0:
            name = string.ascii_lowercase[idx % 26] + name
            idx = (idx // 26) - 1
        return "vd" + name

    def create_domain(self, request):
        """Create a domain based on the `request` with hostname.

        For now this just uses `get_best_network` to connect the interfaces
        of the domain to the network.
        """
        # Create all the block devices first. If cannot complete successfully
        # then fail early. The driver currently doesn't do any tag matching
        # for block devices, and is not really required for Virsh.
        created_disks = []
        for idx, disk in enumerate(request.block_devices):
            try:
                disk_info = self.create_local_volume(disk.size)
            except Exception:
                self.cleanup_disks(created_disks)
                raise
            else:
                if disk_info is None:
                    raise PodInvalidResources(
                        "not enough space for disk %d." % idx)
                else:
                    created_disks.append(disk_info)

        # Construct the domain XML.
        domain_params = self.get_domain_capabilities()
        domain_params['name'] = request.hostname
        domain_params['uuid'] = str(uuid.uuid4())
        domain_params['arch'] = ARCH_FIX_REVERSE[request.architecture]
        domain_params['cores'] = str(request.cores)
        domain_params['memory'] = str(request.memory)
        domain_xml = DOM_TEMPLATE.format(**domain_params)

        # Define the domain in virsh.
        with NamedTemporaryFile() as f:
            f.write(domain_xml.encode('utf-8'))
            f.write(b'\n')
            f.flush()
            self.run(['define', f.name])

        # Attach the created disks in order.
        for idx, (pool, volume) in enumerate(created_disks):
            block_name = self.get_block_name_from_idx(idx)
            self.attach_local_volume(
                request.hostname, pool, volume, block_name)

        # Attach new interfaces to the best possible network.
        best_network = self.get_best_network()
        for _ in request.interfaces:
            self.attach_interface(request.hostname, best_network)

        # Setup the domain to PXE boot.
        self.configure_pxe_boot(request.hostname)

        # Return the result as a discovered machine.
        return self.get_discovered_machine(request.hostname, request=request)

    def delete_domain(self, domain):
        """Delete `domain` and its volumes."""
        # Ensure that its destroyed first.
        self.run(['destroy', domain])
        # Undefine the domains and remove all storage and snapshots.
        self.run([
            'undefine', domain,
            '--remove-all-storage', '--delete-snapshots', '--managed-save'])


class VirshPodDriver(PodDriver):

    name = 'virsh'
    description = "Virsh (virtual systems)"
    settings = [
        make_setting_field(
            'power_address', "Virsh address", required=True),
        make_setting_field(
            'power_pass', "Virsh password (optional)",
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
    def get_virsh_connection(self, context):
        """Connect and return the virsh connection."""
        power_address = context.get('power_address')
        power_pass = context.get('power_pass')
        # Login to Virsh console.
        conn = VirshSSH()
        logged_in = yield deferToThread(conn.login, power_address, power_pass)
        if not logged_in:
            raise VirshError('Failed to login to virsh console.')
        return conn

    @inlineCallbacks
    def discover(self, system_id, context):
        """Discover all resources.

        Returns a defer to a DiscoveredPod object.
        """
        conn = yield self.get_virsh_connection(context)

        # Discover pod resources.
        discovered_pod = yield deferToThread(conn.get_pod_resources)

        # Discovered pod hints.
        discovered_pod.hints = yield deferToThread(conn.get_pod_hints)

        # Discover VMs.
        machines = []
        virtual_machines = yield deferToThread(conn.list_machines)
        for vm in virtual_machines:
            discovered_machine = yield deferToThread(
                conn.get_discovered_machine, vm)
            if discovered_machine is not None:
                discovered_machine.cpu_speed = discovered_pod.cpu_speed
                machines.append(discovered_machine)
        discovered_pod.machines = machines

        # Return the DiscoveredPod
        return discovered_pod

    @inlineCallbacks
    def compose(self, system_id, context, request):
        """Compose machine."""
        conn = yield self.get_virsh_connection(context)
        created_machine = yield deferToThread(conn.create_domain, request)
        hints = yield deferToThread(conn.get_pod_hints)
        return created_machine, hints

    @inlineCallbacks
    def decompose(self, system_id, context):
        """Decompose machine."""
        conn = yield self.get_virsh_connection(context)
        yield deferToThread(conn.delete_domain, context['power_id'])
        hints = yield deferToThread(conn.get_pod_hints)
        return hints


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
            macs, arch, 'virsh', params, domain, hostname=machine).wait(30)

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
