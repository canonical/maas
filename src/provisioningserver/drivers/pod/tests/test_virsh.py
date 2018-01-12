# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod.virsh`."""

__all__ = []

from collections import OrderedDict
import random
from textwrap import dedent
from unittest.mock import (
    ANY,
    call,
    sentinel,
)

from lxml import etree
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
import pexpect
from provisioningserver.drivers.pod import (
    Capabilities,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
    virsh,
    virsh as virsh_module,
)
from provisioningserver.drivers.pod.virsh import VirshPodDriver
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils.shell import (
    get_env_with_locale,
    has_command_available,
)
from provisioningserver.utils.twisted import asynchronous
from testtools.matchers import Equals
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


SAMPLE_DOMBLKINFO = dedent("""
    Capacity:       21474836480
    Allocation:     5563392000
    Physical:       21478375424
    """)

SAMPLE_DOMBLKLIST = dedent("""
    Type       Device     Target     Source
    ------------------------------------------------
    file       disk       vda        /var/lib/libvirt/images/example1.qcow2
    file       disk       vdb        /var/lib/libvirt/images/example2.qcow2
    file       cdrom      hdb        -
    """)

SAMPLE_DOMINFO = dedent("""
    Id:             -
    Name:           example
    UUID:           6376cfa4-d75e-4f4a-bd3d-8fa57b5a3237
    OS Type:        hvm
    State:          shut off
    CPU(s):         1
    Max memory:     1048576 KiB
    Used memory:    1048576 KiB
    Persistent:     yes
    Autostart:      disable
    Managed save:   no
    Security model: apparmor
    Security DOI:   0
    """)

SAMPLE_NODEINFO = dedent("""
    CPU model:           x86_64
    CPU(s):              8
    CPU frequency:       2400 MHz
    CPU socket(s):       1
    Core(s) per socket:  4
    Thread(s) per core:  2
    NUMA cell(s):        1
    Memory size:         16307176 KiB
    """)

SAMPLE_POOLLIST = dedent("""
     Name                 State      Autostart
    -------------------------------------------
     default              active     yes
     ubuntu               active     yes
    """)

SAMPLE_POOLINFO = dedent("""
    Name:           default
    UUID:           59edc0cb-4635-449a-80e2-2c8a59afa327
    State:          running
    Persistent:     yes
    Autostart:      yes
    Capacity:       452.96 GiB
    Allocation:     279.12 GiB
    Available:      173.84 GiB
    """)

SAMPLE_POOLINFO_TB = dedent("""
    Name:           default
    UUID:           59edc0cb-4635-449a-80e2-2c8a59afa327
    State:          running
    Persistent:     yes
    Autostart:      yes
    Capacity:       2.21 TiB
    Allocation:     880.64 GiB
    Available:      1.35 TiB
    """)

SAMPLE_IFLIST = dedent("""
    Interface  Type       Source     Model       MAC
    -------------------------------------------------------
    -          bridge     br0        e1000       %s
    -          bridge     br1        e1000       %s
    """)

SAMPLE_DUMPXML = dedent("""
    <domain type='kvm'>
      <name>test</name>
      <memory unit='KiB'>4096576</memory>
      <currentMemory unit='KiB'>4096576</currentMemory>
      <vcpu placement='static'>1</vcpu>
      <os>
        <type arch='%s'>hvm</type>
        <boot dev='hd'/>
      </os>
    </domain>
    """)

SAMPLE_DUMPXML_2 = dedent("""
    <domain type='kvm'>
      <name>test</name>
      <memory unit='KiB'>4096576</memory>
      <currentMemory unit='KiB'>4096576</currentMemory>
      <vcpu placement='static'>1</vcpu>
      <os>
        <type arch='%s'>hvm</type>
        <boot dev='hd'/>
        <boot dev='network'/>
      </os>
    </domain>
    """)

SAMPLE_DUMPXML_3 = dedent("""
    <domain type='kvm'>
      <name>test</name>
      <memory unit='KiB'>4096576</memory>
      <currentMemory unit='KiB'>4096576</currentMemory>
      <vcpu placement='static'>1</vcpu>
      <os>
        <type arch='%s'>hvm</type>
        <boot dev='network'/>
      </os>
    </domain>
    """)

SAMPLE_DUMPXML_4 = dedent("""
    <domain type='kvm'>
      <name>test</name>
      <memory unit='KiB'>4096576</memory>
      <currentMemory unit='KiB'>4096576</currentMemory>
      <vcpu placement='static'>1</vcpu>
      <os>
        <type arch='%s'>hvm</type>
        <boot dev='network'/>
        <boot dev='hd'/>
      </os>
    </domain>
    """)

SAMPLE_CAPABILITY_KVM = dedent("""\
    <domainCapabilities>
      <path>/usr/bin/qemu-system-x86_64</path>
      <domain>kvm</domain>
      <machine>pc-i440fx-xenial</machine>
      <arch>x86_64</arch>
      <vcpu max='255'/>
      <os supported='yes'>
        <loader supported='yes'>
          <enum name='type'>
            <value>rom</value>
            <value>pflash</value>
          </enum>
          <enum name='readonly'>
            <value>yes</value>
            <value>no</value>
          </enum>
        </loader>
      </os>
      <devices>
        <disk supported='yes'>
          <enum name='diskDevice'>
            <value>disk</value>
            <value>cdrom</value>
            <value>floppy</value>
            <value>lun</value>
          </enum>
          <enum name='bus'>
            <value>ide</value>
            <value>fdc</value>
            <value>scsi</value>
            <value>virtio</value>
            <value>usb</value>
          </enum>
        </disk>
        <hostdev supported='yes'>
          <enum name='mode'>
            <value>subsystem</value>
          </enum>
          <enum name='startupPolicy'>
            <value>default</value>
            <value>mandatory</value>
            <value>requisite</value>
            <value>optional</value>
          </enum>
          <enum name='subsysType'>
            <value>usb</value>
            <value>pci</value>
            <value>scsi</value>
          </enum>
          <enum name='capsType'/>
          <enum name='pciBackend'/>
        </hostdev>
      </devices>
      <features>
        <gic supported='no'/>
      </features>
    </domainCapabilities>
    """)

SAMPLE_CAPABILITY_QEMU = dedent("""\
    <domainCapabilities>
      <path>/usr/bin/qemu-system-x86_64</path>
      <domain>qemu</domain>
      <machine>pc-i440fx-xenial</machine>
      <arch>x86_64</arch>
      <vcpu max='255'/>
      <os supported='yes'>
        <loader supported='yes'>
          <enum name='type'>
            <value>rom</value>
            <value>pflash</value>
          </enum>
          <enum name='readonly'>
            <value>yes</value>
            <value>no</value>
          </enum>
        </loader>
      </os>
      <devices>
        <disk supported='yes'>
          <enum name='diskDevice'>
            <value>disk</value>
            <value>cdrom</value>
            <value>floppy</value>
            <value>lun</value>
          </enum>
          <enum name='bus'>
            <value>ide</value>
            <value>fdc</value>
            <value>scsi</value>
            <value>virtio</value>
            <value>usb</value>
          </enum>
        </disk>
        <hostdev supported='yes'>
          <enum name='mode'>
            <value>subsystem</value>
          </enum>
          <enum name='startupPolicy'>
            <value>default</value>
            <value>mandatory</value>
            <value>requisite</value>
            <value>optional</value>
          </enum>
          <enum name='subsysType'>
            <value>usb</value>
            <value>pci</value>
            <value>scsi</value>
          </enum>
          <enum name='capsType'/>
          <enum name='pciBackend'/>
        </hostdev>
      </devices>
      <features>
        <gic supported='no'/>
      </features>
    </domainCapabilities>
    """)


def make_requested_machine():
    block_devices = [
        RequestedMachineBlockDevice(
            size=random.randint(1024 ** 3, 4 * 1024 ** 3))
        for _ in range(3)
    ]
    interfaces = [
        RequestedMachineInterface()
        for _ in range(3)
    ]
    return RequestedMachine(
        hostname=factory.make_name('hostname'),
        architecture="amd64/generic",
        cores=random.randint(2, 4), memory=random.randint(1024, 4096),
        cpu_speed=random.randint(2000, 3000), block_devices=block_devices,
        interfaces=interfaces)


class TestVirshSSH(MAASTestCase):
    """Tests for `VirshSSH`."""

    def configure_virshssh_pexpect(self, inputs=None, dom_prefix=None):
        """Configures the VirshSSH class to use 'cat' process
        for testing instead of the actual virsh."""
        conn = virsh.VirshSSH(timeout=0.1, dom_prefix=dom_prefix)
        self.addCleanup(conn.close)
        self.patch(conn, '_execute')
        conn._spawn('cat')
        if inputs is not None:
            for line in inputs:
                conn.sendline(line)
        return conn

    def configure_virshssh(self, output, dom_prefix=None):
        self.patch(virsh.VirshSSH, 'run').return_value = output
        return virsh.VirshSSH(dom_prefix=dom_prefix)

    def test_login_prompt(self):
        virsh_outputs = [
            'virsh # '
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.login(poweraddr=None))

    def test_login_with_sshkey(self):
        virsh_outputs = [
            "The authenticity of host '127.0.0.1' can't be established.",
            "ECDSA key fingerprint is "
            "00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff.",
            "Are you sure you want to continue connecting (yes/no)? ",
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_sendline = self.patch(conn, 'sendline')
        conn.login(poweraddr=None)
        self.assertThat(mock_sendline, MockCalledOnceWith('yes'))

    def test_login_with_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.make_ipv4_address(),
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        fake_password = factory.make_name('password')
        mock_sendline = self.patch(conn, 'sendline')
        conn.login(poweraddr=None, password=fake_password)
        self.assertThat(mock_sendline, MockCalledOnceWith(fake_password))

    def test_login_missing_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.make_ipv4_address(),
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, 'close')
        self.assertFalse(conn.login(poweraddr=None, password=None))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_login_invalid(self):
        virsh_outputs = [
            factory.make_string(),
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, 'close')
        self.assertFalse(conn.login(poweraddr=None))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_logout(self):
        conn = self.configure_virshssh_pexpect()
        mock_sendline = self.patch(conn, 'sendline')
        mock_close = self.patch(conn, 'close')
        conn.logout()
        self.assertThat(mock_sendline, MockCalledOnceWith('quit'))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_prompt(self):
        virsh_outputs = [
            'virsh # '
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.prompt())

    def test_invalid_prompt(self):
        virsh_outputs = [
            factory.make_string()
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertFalse(conn.prompt())

    def test_run(self):
        cmd = ['list', '--all', '--name']
        expected = ' '.join(cmd)
        names = [factory.make_name('machine') for _ in range(3)]
        conn = self.configure_virshssh_pexpect()
        conn.before = ('\n'.join([expected] + names)).encode("utf-8")
        mock_sendline = self.patch(conn, 'sendline')
        mock_prompt = self.patch(conn, 'prompt')
        output = conn.run(cmd)
        self.assertThat(mock_sendline, MockCalledOnceWith(expected))
        self.assertThat(mock_prompt, MockCalledOnceWith())
        self.assertEqual('\n'.join(names), output)

    def test_get_column_values(self):
        keys = ['Source', 'Model']
        expected = (('br0', 'e1000'), ('br1', 'e1000'))
        conn = self.configure_virshssh('')
        values = conn.get_column_values(SAMPLE_IFLIST, keys)
        self.assertItemsEqual(values, expected)

    def test_get_key_value(self):
        key = 'CPU model'
        expected = 'x86_64'
        conn = self.configure_virshssh('')
        value = conn.get_key_value(SAMPLE_NODEINFO, key)
        self.assertEquals(value, expected)

    def test_list_machines(self):
        names = [factory.make_name('machine') for _ in range(3)]
        conn = self.configure_virshssh('\n'.join(names))
        expected = conn.list_machines()
        self.assertItemsEqual(names, expected)

    def test_list_machines_with_dom_prefix(self):
        prefix = 'dom_prefix'
        names = [prefix + factory.make_name('machine') for _ in range(3)]
        conn = self.configure_virshssh('\n'.join(names), dom_prefix=prefix)
        expected = conn.list_machines()
        self.assertItemsEqual(names, expected)

    def test_list_pools(self):
        names = ['default', 'ubuntu']
        conn = self.configure_virshssh(SAMPLE_POOLLIST)
        expected = conn.list_pools()
        self.assertItemsEqual(names, expected)

    def test_list_machine_block_devices(self):
        block_devices = ('vda', 'vdb')
        conn = self.configure_virshssh(SAMPLE_DOMBLKLIST)
        expected = conn.list_machine_block_devices(
            factory.make_name('machine'))
        self.assertItemsEqual(block_devices, expected)

    def test_get_machine_state(self):
        state = factory.make_name('state')
        conn = self.configure_virshssh(state)
        expected = conn.get_machine_state('')
        self.assertEqual(state, expected)

    def test_get_machine_state_error(self):
        conn = self.configure_virshssh('error:')
        expected = conn.get_machine_state('')
        self.assertEqual(None, expected)

    def test_machine_mac_addresses_returns_list(self):
        macs = [factory.make_mac_address() for _ in range(2)]
        output = SAMPLE_IFLIST % (macs[0], macs[1])
        conn = self.configure_virshssh(output)
        expected = conn.list_machine_mac_addresses('')
        self.assertEqual(macs, expected)

    def test_list_machine_mac_addresses_error(self):
        conn = self.configure_virshssh('error:')
        expected = conn.get_machine_state('')
        self.assertEqual(None, expected)

    def test_get_pod_cpu_count(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        expected = conn.get_pod_cpu_count()
        self.assertEqual(8, expected)

    def test_get_machine_cpu_count(self):
        conn = self.configure_virshssh(SAMPLE_DOMINFO)
        expected = conn.get_machine_cpu_count(factory.make_name('machine'))
        self.assertEqual(1, expected)

    def test_get_pod_cpu_speed(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        expected = conn.get_pod_cpu_speed()
        self.assertEqual(2400, expected)

    def test_get_pod_memory(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        expected = conn.get_pod_memory()
        self.assertEqual(int(16307176 / 1024), expected)

    def test_get_machine_memory(self):
        conn = self.configure_virshssh(SAMPLE_DOMINFO)
        expected = conn.get_machine_memory(factory.make_name('machine'))
        self.assertEqual(int(1048576 / 1024), expected)

    def test_get_pod_pool_size_map(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO)
        pools_mock = self.patch(virsh.VirshSSH, 'list_pools')
        pools_mock.return_value = [
            factory.make_name('pool') for _ in range(3)]
        expected = conn.get_pod_pool_size_map('Capacity')
        capacity = int(452.96 * 2**30)
        self.assertEqual({
            pool: capacity
            for pool in pools_mock.return_value
        }, expected)

    def test_get_pod_pool_size_map_terabytes(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO_TB)
        pools_mock = self.patch(virsh.VirshSSH, 'list_pools')
        pools_mock.return_value = [
            factory.make_name('pool') for _ in range(3)]
        expected = conn.get_pod_pool_size_map('Capacity')
        capacity = int(2.21 * 2**40)
        self.assertEqual({
            pool: capacity
            for pool in pools_mock.return_value
        }, expected)

    def test_get_pod_local_storage(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO)
        pools_mock = self.patch(virsh.VirshSSH, 'list_pools')
        pools_mock.return_value = [
            factory.make_name('pool') for _ in range(3)]
        expected = conn.get_pod_local_storage()
        self.assertEqual(int(452.96 * 3 * 2**30), expected)

    def test_get_pod_local_storage_no_pool(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO)
        pools_mock = self.patch(virsh.VirshSSH, 'list_pools')
        pools_mock.return_value = []
        self.assertRaises(PodInvalidResources, conn.get_pod_local_storage)

    def test_get_pod_available_local_storage(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO)
        pools_mock = self.patch(virsh.VirshSSH, 'list_pools')
        pools_mock.return_value = [
            factory.make_name('pool') for _ in range(3)]
        expected = conn.get_pod_available_local_storage()
        self.assertEqual(int(173.84 * 3 * 2**30), expected)

    def test_get_machine_local_storage(self):
        conn = self.configure_virshssh(SAMPLE_DOMBLKINFO)
        expected = conn.get_machine_local_storage(
            factory.make_name('machine'),
            factory.make_name('device'))
        self.assertEqual(21474836480, expected)

    def test_get_machine_local_storage_handles_no_output(self):
        conn = self.configure_virshssh('')
        expected = conn.get_machine_local_storage(
            factory.make_name('machine'),
            factory.make_name('device'))
        self.assertIsNone(expected)

    def test_get_pod_arch(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        expected = conn.get_pod_arch()
        self.assertEqual('amd64/generic', expected)

    def test_get_machine_arch_returns_valid(self):
        arch = factory.make_name('arch')
        output = SAMPLE_DUMPXML % arch
        conn = self.configure_virshssh(output)
        expected = conn.get_machine_arch('')
        self.assertEqual(arch, expected)

    def test_get_machine_arch_returns_valid_fixed(self):
        arch = random.choice(list(virsh.ARCH_FIX))
        fixed_arch = virsh.ARCH_FIX[arch]
        output = SAMPLE_DUMPXML % arch
        conn = self.configure_virshssh(output)
        expected = conn.get_machine_arch('')
        self.assertEqual(fixed_arch, expected)

    def test__get_pod_resources(self):
        conn = self.configure_virshssh('')
        architecture = factory.make_name('arch')
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        local_storage = random.randint(4096, 8192)
        mock_get_pod_arch = self.patch(
            virsh.VirshSSH, 'get_pod_arch')
        mock_get_pod_cpu_count = self.patch(
            virsh.VirshSSH, 'get_pod_cpu_count')
        mock_get_pod_cpu_speed = self.patch(
            virsh.VirshSSH, 'get_pod_cpu_speed')
        mock_get_pod_memory = self.patch(
            virsh.VirshSSH, 'get_pod_memory')
        mock_get_pod_local_storage = self.patch(
            virsh.VirshSSH, 'get_pod_local_storage')
        mock_get_pod_arch.return_value = architecture
        mock_get_pod_cpu_count.return_value = cores
        mock_get_pod_cpu_speed.return_value = cpu_speed
        mock_get_pod_memory.return_value = memory
        mock_get_pod_local_storage.return_value = local_storage

        discovered_pod = conn.get_pod_resources()
        self.assertEquals([architecture], discovered_pod.architectures)
        self.assertEquals([
            Capabilities.COMPOSABLE,
            Capabilities.DYNAMIC_LOCAL_STORAGE,
            Capabilities.OVER_COMMIT], discovered_pod.capabilities)
        self.assertEquals(cores, discovered_pod.cores)
        self.assertEquals(cpu_speed, discovered_pod.cpu_speed)
        self.assertEquals(memory, discovered_pod.memory)
        self.assertEquals(local_storage, discovered_pod.local_storage)

    def test__get_pod_hints(self):
        conn = self.configure_virshssh('')
        cores = random.randint(8, 16)
        memory = random.randint(4096, 8192)
        cpu_speed = random.randint(2000, 3000)
        local_storage = random.randint(4096, 8192)
        mock_get_pod_cores = self.patch(
            virsh.VirshSSH, 'get_pod_cpu_count')
        mock_get_pod_cores.return_value = cores
        mock_get_pod_memory = self.patch(
            virsh.VirshSSH, 'get_pod_memory')
        mock_get_pod_memory.return_value = memory
        mock_get_pod_cpu_speed = self.patch(
            virsh.VirshSSH, 'get_pod_cpu_speed')
        mock_get_pod_cpu_speed.return_value = cpu_speed
        mock_get_pod_available_local_storage = self.patch(
            virsh.VirshSSH, 'get_pod_available_local_storage')
        mock_get_pod_available_local_storage.return_value = local_storage

        discovered_pod_hints = conn.get_pod_hints()
        self.assertEquals(cores, discovered_pod_hints.cores)
        self.assertEquals(memory, discovered_pod_hints.memory)
        self.assertEquals(cpu_speed, discovered_pod_hints.cpu_speed)
        self.assertEquals(
            local_storage, discovered_pod_hints.local_storage)

    def test__get_discovered_machine(self):
        conn = self.configure_virshssh('')
        hostname = factory.make_name('hostname')
        architecture = factory.make_name('arch')
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)
        devices = [
            factory.make_name('device') for _ in range(3)
        ]
        device_tags = [
            [
                factory.make_name('tag')
                for _ in range(3)
            ]
            for _ in range(3)
        ]
        local_storage = [
            random.randint(4096, 8192) for _ in range(3)
        ]
        mac_addresses = [
            factory.make_mac_address() for _ in range(3)
        ]
        mock_get_machine_arch = self.patch(
            virsh.VirshSSH, 'get_machine_arch')
        mock_get_machine_cpu_count = self.patch(
            virsh.VirshSSH, 'get_machine_cpu_count')
        mock_get_machine_memory = self.patch(
            virsh.VirshSSH, 'get_machine_memory')
        mock_get_machine_state = self.patch(
            virsh.VirshSSH, 'get_machine_state')
        mock_list_machine_block_devices = self.patch(
            virsh.VirshSSH, 'list_machine_block_devices')
        mock_get_machine_local_storage = self.patch(
            virsh.VirshSSH, 'get_machine_local_storage')
        mock_list_machine_mac_addresses = self.patch(
            virsh.VirshSSH, 'list_machine_mac_addresses')
        mock_get_machine_arch.return_value = architecture
        mock_get_machine_cpu_count.return_value = cores
        mock_get_machine_memory.return_value = memory
        mock_get_machine_state.return_value = "shut off"
        mock_list_machine_block_devices.return_value = devices
        mock_get_machine_local_storage.side_effect = local_storage
        mock_list_machine_mac_addresses.return_value = mac_addresses

        block_devices = [
            RequestedMachineBlockDevice(
                size=local_storage[idx], tags=device_tags[idx])
            for idx in range(3)
        ]
        # None of the parameters matter in the RequestedMachine except for
        # block_device. All other paramters are ignored by this method.
        request = RequestedMachine(
            hostname=None, architecture='', cores=0, memory=0, interfaces=[],
            block_devices=block_devices)
        discovered_machine = conn.get_discovered_machine(
            hostname, request=request)
        self.assertEquals(hostname, discovered_machine.hostname)
        self.assertEquals(architecture, discovered_machine.architecture)
        self.assertEquals(cores, discovered_machine.cores)
        self.assertEquals(memory, discovered_machine.memory)
        self.assertItemsEqual(
            local_storage,
            [bd.size for bd in discovered_machine.block_devices])
        self.assertItemsEqual(
            device_tags,
            [bd.tags for bd in discovered_machine.block_devices])
        self.assertItemsEqual(
            mac_addresses,
            [m.mac_address for m in discovered_machine.interfaces])
        self.assertTrue(discovered_machine.interfaces[0].boot)
        self.assertFalse(discovered_machine.interfaces[1].boot)
        self.assertFalse(discovered_machine.interfaces[2].boot)

    def test__get_discovered_machine_handles_bad_storage_device(self):
        conn = self.configure_virshssh('')
        hostname = factory.make_name('hostname')
        architecture = factory.make_name('arch')
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)
        devices = [
            factory.make_name('device') for _ in range(3)
        ]
        local_storage = [
            random.randint(4096, 8192) for _ in range(2)
        ] + [None]  # Last storage device is bad.
        mac_addresses = [
            factory.make_mac_address() for _ in range(3)
        ]
        mock_get_machine_arch = self.patch(
            virsh.VirshSSH, 'get_machine_arch')
        mock_get_machine_cpu_count = self.patch(
            virsh.VirshSSH, 'get_machine_cpu_count')
        mock_get_machine_memory = self.patch(
            virsh.VirshSSH, 'get_machine_memory')
        mock_get_machine_state = self.patch(
            virsh.VirshSSH, 'get_machine_state')
        mock_list_machine_block_devices = self.patch(
            virsh.VirshSSH, 'list_machine_block_devices')
        mock_get_machine_local_storage = self.patch(
            virsh.VirshSSH, 'get_machine_local_storage')
        mock_list_machine_mac_addresses = self.patch(
            virsh.VirshSSH, 'list_machine_mac_addresses')
        mock_get_machine_arch.return_value = architecture
        mock_get_machine_cpu_count.return_value = cores
        mock_get_machine_memory.return_value = memory
        mock_get_machine_state.return_value = "shut off"
        mock_list_machine_block_devices.return_value = devices
        mock_get_machine_local_storage.side_effect = local_storage
        mock_list_machine_mac_addresses.return_value = mac_addresses

        discovered_machine = conn.get_discovered_machine(hostname)
        self.assertIsNone(discovered_machine)

    def test_poweron(self):
        conn = self.configure_virshssh('')
        expected = conn.poweron(factory.make_name('machine'))
        self.assertEqual(True, expected)

    def test_poweron_error(self):
        conn = self.configure_virshssh('error:')
        expected = conn.poweron(factory.make_name('machine'))
        self.assertEqual(False, expected)

    def test_poweroff(self):
        conn = self.configure_virshssh('')
        expected = conn.poweroff(factory.make_name('machine'))
        self.assertEqual(True, expected)

    def test_poweroff_error(self):
        conn = self.configure_virshssh('error:')
        expected = conn.poweroff(factory.make_name('machine'))
        self.assertEqual(False, expected)

    def test_resets_locale(self):
        """
        VirshSSH resets the locale to ensure we only ever get English strings.
        """
        c_utf8_environment = get_env_with_locale()
        mock_spawn = self.patch(pexpect.spawn, "__init__")
        self.configure_virshssh('')
        self.assertThat(
            mock_spawn,
            MockCalledOnceWith(
                None, timeout=30, maxread=2000, env=c_utf8_environment))

    def test_get_usable_pool(self):
        conn = self.configure_virshssh('')
        pools = OrderedDict([(
            factory.make_name("pool"),
            random.randint(i * 1000, (i + 1) * 1000))
            for i in range(3)
        ])
        size = random.randint(
            list(pools.values())[0] + 1, list(pools.values())[1] + 1)
        self.patch(
            virsh.VirshSSH, "get_pod_pool_size_map").return_value = pools
        self.assertEqual(
            list(pools.keys())[1],
            conn.get_usable_pool(size))

    def test_create_local_volume_returns_None(self):
        conn = self.configure_virshssh('')
        self.patch(
            virsh.VirshSSH, "get_usable_pool").return_value = None
        self.assertIsNone(conn.create_local_volume(random.randint(1000, 2000)))

    def test_create_local_volume_makes_call_returns_pool_and_volume(self):
        conn = self.configure_virshssh('')
        pool = factory.make_name('pool')
        self.patch(
            virsh.VirshSSH, "get_usable_pool").return_value = pool
        mock_run = self.patch(virsh.VirshSSH, "run")
        volume_size = random.randint(1000, 2000)
        used_pool, volume_name = conn.create_local_volume(volume_size)
        self.assertThat(mock_run, MockCalledOnceWith([
            'vol-create-as', used_pool, volume_name, str(volume_size),
            '--allocation', '0', '--format', 'raw']))
        self.assertEqual(pool, used_pool)
        self.assertIsNotNone(volume_name)

    def test_delete_local_volume(self):
        conn = self.configure_virshssh('')
        pool = factory.make_name('pool')
        volume_name = factory.make_name('volume')
        mock_run = self.patch(virsh.VirshSSH, "run")
        conn.delete_local_volume(pool, volume_name)
        self.assertThat(mock_run, MockCalledOnceWith([
            'vol-delete', volume_name, '--pool', pool]))

    def test_get_volume_path(self):
        conn = self.configure_virshssh('')
        pool = factory.make_name('pool')
        volume_name = factory.make_name('volume')
        volume_path = factory.make_name('path')
        mock_run = self.patch(virsh.VirshSSH, "run")
        mock_run.return_value = "   %s    " % volume_path
        self.assertEqual(volume_path, conn.get_volume_path(pool, volume_name))
        self.assertThat(mock_run, MockCalledOnceWith([
            'vol-path', volume_name, '--pool', pool]))

    def test_attach_local_volume(self):
        conn = self.configure_virshssh('')
        domain = factory.make_name('domain')
        pool = factory.make_name('pool')
        volume_name = factory.make_name('volume')
        volume_path = factory.make_name('path')
        device_name = factory.make_name('device')
        mock_run = self.patch(virsh.VirshSSH, "run")
        self.patch(
            virsh.VirshSSH, "get_volume_path").return_value = volume_path
        conn.attach_local_volume(domain, pool, volume_name, device_name)
        self.assertThat(mock_run, MockCalledOnceWith([
            'attach-disk', domain, volume_path, device_name,
            '--targetbus', 'virtio', '--sourcetype', 'file', '--config']))

    def test_get_networks_list(self):
        networks = [
            factory.make_name('network')
            for _ in range(3)
        ]
        conn = self.configure_virshssh('\n'.join(networks))
        self.assertEquals(networks, conn.get_network_list())

    def test_get_best_network_returns_maas(self):
        conn = self.configure_virshssh('')
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            'maas', 'default', 'other']
        self.assertEquals('maas', conn.get_best_network())

    def test_get_best_network_returns_default(self):
        conn = self.configure_virshssh('')
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            'default', 'other']
        self.assertEquals('default', conn.get_best_network())

    def test_get_best_network_returns_first(self):
        conn = self.configure_virshssh('')
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            'first', 'second']
        self.assertEquals('first', conn.get_best_network())

    def test_get_best_network_no_network(self):
        conn = self.configure_virshssh('')
        self.patch(virsh.VirshSSH, "get_network_list").return_value = []
        self.assertRaises(PodInvalidResources, conn.get_best_network)

    def test_attach_interface(self):
        conn = self.configure_virshssh('')
        domain = factory.make_name('domain')
        network = factory.make_name('network')
        mock_run = self.patch(virsh.VirshSSH, "run")
        conn.attach_interface(domain, network)
        self.assertThat(mock_run, MockCalledOnceWith([
            'attach-interface', domain, 'network', network,
            '--model', 'virtio', '--config']))

    def test_get_domain_capabilities_for_kvm(self):
        conn = self.configure_virshssh(SAMPLE_CAPABILITY_KVM)
        self.assertEqual({
            'type': 'kvm',
            'emulator': '/usr/bin/qemu-system-x86_64',
        }, conn.get_domain_capabilities())

    def test_get_domain_capabilities_for_qemu(self):
        conn = self.configure_virshssh('')
        self.patch(virsh.VirshSSH, "run").side_effect = [
            factory.make_exception(),
            SAMPLE_CAPABILITY_QEMU,
        ]
        self.assertEqual({
            'type': 'qemu',
            'emulator': '/usr/bin/qemu-system-x86_64',
        }, conn.get_domain_capabilities())

    def test_get_domain_capabilities_raises_error(self):
        conn = self.configure_virshssh('error: some error')
        self.assertRaises(virsh.VirshError, conn.get_domain_capabilities)

    def test_cleanup_disks_deletes_all(self):
        conn = self.configure_virshssh('')
        volumes = [
            (factory.make_name('pool'), factory.make_name('vol'))
            for _ in range(3)
        ]
        mock_delete = self.patch(virsh.VirshSSH, "delete_local_volume")
        conn.cleanup_disks(volumes)
        self.assertThat(mock_delete, MockCallsMatch(*[
            call(pool, vol)
            for pool, vol in volumes
        ]))

    def test_cleanup_disks_catches_all_exceptions(self):
        conn = self.configure_virshssh('')
        volumes = [
            (factory.make_name('pool'), factory.make_name('vol'))
            for _ in range(3)
        ]
        mock_delete = self.patch(virsh.VirshSSH, "delete_local_volume")
        mock_delete.side_effect = factory.make_exception()
        # Tests that no exception is raised.
        conn.cleanup_disks(volumes)

    def test_get_block_name_from_idx(self):
        conn = self.configure_virshssh('')
        expected = [
            (0, 'vda'),
            (25, 'vdz'),
            (26, 'vdaa'),
            (27, 'vdab'),
            (51, 'vdaz'),
            (52, 'vdba'),
            (53, 'vdbb'),
            (701, 'vdzz'),
            (702, 'vdaaa'),
            (703, 'vdaab'),
            (18277, 'vdzzz'),
        ]
        for idx, name in expected:
            self.expectThat(conn.get_block_name_from_idx(idx), Equals(name))

    def test_create_domain_fails_on_disk_create(self):
        conn = self.configure_virshssh('')
        request = make_requested_machine()
        exception_type = factory.make_exception_type()
        exception = factory.make_exception(bases=(exception_type,))
        first_pool, first_vol = (
            factory.make_name('pool'), factory.make_name('vol'))
        self.patch(virsh.VirshSSH, "create_local_volume").side_effect = [
            (first_pool, first_vol),
            exception
        ]
        mock_cleanup = self.patch(virsh.VirshSSH, "cleanup_disks")
        error = self.assertRaises(exception_type, conn.create_domain, request)
        self.assertThat(
            mock_cleanup, MockCalledOnceWith([(first_pool, first_vol)]))
        self.assertIs(exception, error)

    def test_create_domain_handles_no_space(self):
        conn = self.configure_virshssh('')
        request = make_requested_machine()
        self.patch(virsh.VirshSSH, "create_local_volume").return_value = None
        error = self.assertRaises(
            PodInvalidResources, conn.create_domain, request, )
        self.assertEqual("not enough space for disk 0.", str(error))

    def test_create_domain_calls_correct_methods(self):
        conn = self.configure_virshssh('')
        request = make_requested_machine()
        request.block_devices = request.block_devices[:1]
        request.interfaces = request.interfaces[:1]
        disk_info = (factory.make_name('pool'), factory.make_name('vol'))
        self.patch(
            virsh.VirshSSH, "create_local_volume").return_value = disk_info
        self.patch(virsh.VirshSSH, "get_domain_capabilities").return_value = {
            "type": "kvm",
            "emulator": "/usr/bin/qemu-system-x86_64",
        }
        self.patch(virsh.VirshSSH, "get_best_network").return_value = "maas"
        mock_run = self.patch(virsh.VirshSSH, "run")
        mock_attach_disk = self.patch(virsh.VirshSSH, "attach_local_volume")
        mock_attach_nic = self.patch(virsh.VirshSSH, "attach_interface")
        mock_configure_pxe = self.patch(virsh.VirshSSH, "configure_pxe_boot")
        mock_discovered = self.patch(virsh.VirshSSH, "get_discovered_machine")
        mock_discovered.return_value = sentinel.discovered
        observed = conn.create_domain(request)
        self.assertThat(mock_run, MockCalledOnceWith(['define', ANY]))
        self.assertThat(
            mock_attach_disk,
            MockCalledOnceWith(ANY, disk_info[0], disk_info[1], 'vda'))
        self.assertThat(
            mock_attach_nic, MockCalledOnceWith(ANY, 'maas'))
        self.assertThat(
            mock_configure_pxe, MockCalledOnceWith(ANY))
        self.assertThat(
            mock_discovered, MockCalledOnceWith(ANY, request=request))
        self.assertEquals(sentinel.discovered, observed)

    def test_delete_domain_calls_correct_methods(self):
        conn = self.configure_virshssh('')
        mock_run = self.patch(virsh.VirshSSH, "run")
        domain = factory.make_name('vm')
        conn.delete_domain(domain)
        self.assertThat(mock_run, MockCallsMatch(
            call(['destroy', domain]),
            call([
                'undefine', domain,
                '--remove-all-storage',
                '--delete-snapshots',
                '--managed-save'])))


class TestVirsh(MAASTestCase):
    """Tests for `probe_virsh_and_enlist`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def _probe_and_enlist_mock_run(self, *args):
        args = args[0]
        # if the argument is "define", we want to ensure that the boot
        # order has been set up correctly.
        if args[0] == "define":
            xml_file = args[1]
            with open(xml_file) as f:
                xml = f.read()
                doc = etree.XML(xml)
                evaluator = etree.XPathEvaluator(doc)
                boot_elements = evaluator(virsh.XPATH_BOOT)
                self.assertEqual(2, len(boot_elements))
                # make sure we set the network to come first, then the HD
                self.assertEqual('network', boot_elements[0].attrib['dev'])
                self.assertEqual('hd', boot_elements[1].attrib['dev'])
        return ""

    @inlineCallbacks
    def test_probe_and_enlist(self):
        # Patch VirshSSH list so that some machines are returned
        # with some fake architectures.
        user = factory.make_name('user')
        system_id = factory.make_name('system_id')
        machines = [factory.make_name('machine') for _ in range(5)]
        self.patch(virsh.VirshSSH, 'list_machines').return_value = machines
        fake_arch = factory.make_name('arch')
        mock_arch = self.patch(virsh.VirshSSH, 'get_machine_arch')
        mock_arch.return_value = fake_arch
        domain = factory.make_name('domain')

        # Patch get_state so that one of the machines is on, so we
        # can check that it will be forced off.
        fake_states = [
            virsh.VirshVMState.ON,
            virsh.VirshVMState.OFF,
            virsh.VirshVMState.OFF,
            virsh.VirshVMState.ON,
            virsh.VirshVMState.ON,
            ]
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.side_effect = fake_states

        # Setup the power parameters that we should expect to be
        # the output of the probe_and_enlist
        fake_password = factory.make_string()
        poweraddr = factory.make_name('poweraddr')
        called_params = []
        fake_macs = []
        for machine in machines:
            macs = [factory.make_mac_address() for _ in range(4)]
            fake_macs.append(macs)
            called_params.append({
                'power_address': poweraddr,
                'power_id': machine,
                'power_pass': fake_password,
                })

        # Patch the get_mac_addresses so we get a known list of
        # mac addresses for each machine.
        mock_macs = self.patch(virsh.VirshSSH, 'list_machine_mac_addresses')
        mock_macs.side_effect = fake_macs

        # Patch the poweroff and create as we really don't want these
        # actions to occur, but want to also check that they are called.
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')
        mock_create_node = self.patch(virsh, 'create_node')
        mock_create_node.side_effect = asynchronous(
            lambda *args, **kwargs: None if machines[4] in args else system_id)
        mock_commission_node = self.patch(virsh, 'commission_node')

        # Patch login and logout so that we don't really contact
        # a server at the fake poweraddr
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_logout = self.patch(virsh.VirshSSH, 'logout')
        mock_get_machine_xml = self.patch(virsh.VirshSSH, 'get_machine_xml')
        mock_get_machine_xml.side_effect = [
            SAMPLE_DUMPXML,
            SAMPLE_DUMPXML_2,
            SAMPLE_DUMPXML_3,
            SAMPLE_DUMPXML_4,
            SAMPLE_DUMPXML,
        ]

        mock_run = self.patch(virsh.VirshSSH, 'run')
        mock_run.side_effect = self._probe_and_enlist_mock_run

        # Perform the probe and enlist
        yield deferToThread(
            virsh.probe_virsh_and_enlist, user, poweraddr,
            fake_password, accept_all=True, domain=domain)

        # Check that login was called with the provided poweraddr and
        # password.
        self.expectThat(
            mock_login, MockCalledOnceWith(poweraddr, fake_password))

        # Check that the create command had the correct parameters for
        # each machine.
        self.expectThat(
            mock_create_node, MockCallsMatch(
                call(
                    fake_macs[0], fake_arch, 'virsh', called_params[0],
                    domain, hostname=machines[0]),
                call(
                    fake_macs[1], fake_arch, 'virsh', called_params[1],
                    domain, hostname=machines[1]),
                call(
                    fake_macs[2], fake_arch, 'virsh', called_params[2],
                    domain, hostname=machines[2]),
                call(
                    fake_macs[3], fake_arch, 'virsh', called_params[3],
                    domain, hostname=machines[3]),
                call(
                    fake_macs[4], fake_arch, 'virsh', called_params[4],
                    domain, hostname=machines[4]),
            ))

        # The first and last machine should have poweroff called on it, as it
        # was initial in the on state.
        self.expectThat(
            mock_poweroff, MockCallsMatch(
                call(machines[0]),
                call(machines[3]),
                call(machines[4]),
            ))

        self.assertThat(mock_logout, MockCalledOnceWith())
        self.expectThat(
            mock_commission_node, MockCallsMatch(
                call(system_id, user),
                call(system_id, user),
                call(system_id, user),
                call(system_id, user),
                call(system_id, user),
            ))

    @inlineCallbacks
    def test_probe_and_enlist_login_failure(self):
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield deferToThread(
                virsh.probe_virsh_and_enlist, user, poweraddr,
                password=factory.make_string(),
                domain=factory.make_string())


class TestVirshPodDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = virsh_module.VirshPodDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual(['libvirt-bin'], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = virsh_module.VirshPodDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_context(self):
        return {
            'system_id': factory.make_name('system_id'),
            'power_address': factory.make_name('power_address'),
            'power_id': factory.make_name('power_id'),
            'power_pass': factory.make_name('power_pass'),
        }

    def test_power_on_calls_power_control_virsh(self):
        power_change = 'on'
        context = self.make_context()
        driver = VirshPodDriver()
        power_control_virsh = self.patch(driver, 'power_control_virsh')
        driver.power_on(context.get('system_id'), context)

        self.assertThat(
            power_control_virsh, MockCalledOnceWith(
                power_change=power_change, **context))

    def test_power_off_calls_power_control_virsh(self):
        power_change = 'off'
        context = self.make_context()
        driver = VirshPodDriver()
        power_control_virsh = self.patch(driver, 'power_control_virsh')
        driver.power_off(context.get('system_id'), context)

        self.assertThat(
            power_control_virsh, MockCalledOnceWith(
                power_change=power_change, **context))

    def test_power_query_calls_power_state_virsh(self):
        power_state = 'off'
        context = self.make_context()
        driver = VirshPodDriver()
        power_state_virsh = self.patch(driver, 'power_state_virsh')
        power_state_virsh.return_value = power_state
        expected_result = driver.power_query(
            context.get('system_id'), context)

        self.expectThat(
            power_state_virsh, MockCalledOnceWith(**context))
        self.expectThat(expected_result, Equals(power_state))

    @inlineCallbacks
    def test_power_control_login_failure(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield driver.power_control_virsh(
                factory.make_name('power_address'),
                factory.make_name('power_id'),
                factory.make_name('power_change'),
                power_pass=factory.make_string())

    @inlineCallbacks
    def test_power_control_on(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = virsh.VirshVMState.OFF
        mock_poweron = self.patch(virsh.VirshSSH, 'poweron')

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        yield driver.power_control_virsh(power_address, power_id, 'on')

        self.assertThat(
            mock_login, MockCalledOnceWith(power_address, None))
        self.assertThat(
            mock_state, MockCalledOnceWith(power_id))
        self.assertThat(
            mock_poweron, MockCalledOnceWith(power_id))

    @inlineCallbacks
    def test_power_control_off(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        yield driver.power_control_virsh(power_address, power_id, 'off')

        self.assertThat(
            mock_login, MockCalledOnceWith(power_address, None))
        self.assertThat(
            mock_state, MockCalledOnceWith(power_id))
        self.assertThat(
            mock_poweroff, MockCalledOnceWith(power_id))

    @inlineCallbacks
    def test_power_control_bad_domain(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = None

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        with ExpectedException(virsh.VirshError):
            yield driver.power_control_virsh(
                power_address, power_id, 'on')

    @inlineCallbacks
    def test_power_control_power_failure(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')
        mock_poweroff.return_value = False

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        with ExpectedException(virsh.VirshError):
            yield driver.power_control_virsh(
                power_address, power_id, 'off')

    @inlineCallbacks
    def test_power_state_login_failure(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield driver.power_state_virsh(
                factory.make_name('power_address'),
                factory.make_name('power_id'),
                power_pass=factory.make_string())

    @inlineCallbacks
    def test_power_state_get_on(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = virsh.VirshVMState.ON

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        state = yield driver.power_state_virsh(power_address, power_id)
        self.assertEqual('on', state)

    @inlineCallbacks
    def test_power_state_get_off(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = virsh.VirshVMState.OFF

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        state = yield driver.power_state_virsh(power_address, power_id)
        self.assertEqual('off', state)

    @inlineCallbacks
    def test_power_state_bad_domain(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = None

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        with ExpectedException(virsh.VirshError):
            yield driver.power_state_virsh(
                power_address, power_id)

    @inlineCallbacks
    def test_power_state_error_on_unknown_state(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_machine_state')
        mock_state.return_value = 'unknown'

        power_address = factory.make_name('power_address')
        power_id = factory.make_name('power_id')
        with ExpectedException(virsh.VirshError):
            yield driver.power_state_virsh(
                power_address, power_id)

    @inlineCallbacks
    def test_discover_errors_on_failed_login(self):
        driver = VirshPodDriver()
        system_id = factory.make_name('system_id')
        context = {
            'power_address': factory.make_name('power_address'),
            'power_pass': factory.make_name('power_pass')
        }
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield driver.discover(system_id, context)

    @inlineCallbacks
    def test_discover(self):
        driver = VirshPodDriver()
        system_id = factory.make_name('system_id')
        context = {
            'power_address': factory.make_name('power_address'),
            'power_pass': factory.make_name('power_pass')
        }
        machines = [
            factory.make_name('machine')
            for _ in range(3)
        ]
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_get_pod_resources = self.patch(
            virsh.VirshSSH, 'get_pod_resources')
        mock_get_pod_hints = self.patch(
            virsh.VirshSSH, 'get_pod_hints')
        mock_list_machines = self.patch(virsh.VirshSSH, 'list_machines')
        mock_get_discovered_machine = self.patch(
            virsh.VirshSSH, 'get_discovered_machine')
        mock_list_machines.return_value = machines

        yield driver.discover(system_id, context)
        self.expectThat(
            mock_get_pod_resources, MockCalledOnceWith())
        self.expectThat(
            mock_get_pod_hints, MockCalledOnceWith())
        self.expectThat(
            mock_list_machines, MockCalledOnceWith())
        self.expectThat(
            mock_get_discovered_machine, MockCallsMatch(
                call(machines[0]),
                call(machines[1]),
                call(machines[2])))

    @inlineCallbacks
    def test_compose(self):
        driver = VirshPodDriver()
        system_id = factory.make_name('system_id')
        context = {
            'power_address': factory.make_name('power_address'),
            'power_pass': factory.make_name('power_pass')
        }
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_create_domain = self.patch(virsh.VirshSSH, 'create_domain')
        mock_create_domain.return_value = sentinel.discovered
        mock_get_pod_hints = self.patch(virsh.VirshSSH, 'get_pod_hints')
        mock_get_pod_hints.return_value = sentinel.hints

        discovered, hints = yield driver.compose(
            system_id, context, make_requested_machine())
        self.assertEquals(sentinel.discovered, discovered)
        self.assertEquals(sentinel.hints, hints)

    @inlineCallbacks
    def test_decompose(self):
        driver = VirshPodDriver()
        system_id = factory.make_name('system_id')
        context = {
            'power_address': factory.make_name('power_address'),
            'power_pass': factory.make_name('power_pass'),
            'power_id': factory.make_name('power_id'),
        }
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        self.patch(virsh.VirshSSH, 'delete_domain')
        mock_get_pod_hints = self.patch(virsh.VirshSSH, 'get_pod_hints')
        mock_get_pod_hints.return_value = sentinel.hints

        hints = yield driver.decompose(system_id, context)
        self.assertEquals(sentinel.hints, hints)
