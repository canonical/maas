# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from math import floor
import os
import random
from textwrap import dedent
from unittest.mock import ANY, call, MagicMock, sentinel
from uuid import uuid4

from lxml import etree
import pexpect
from testtools.matchers import Equals
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredPodStoragePool,
    InterfaceAttachType,
    KnownHostInterface,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
    virsh,
)
from provisioningserver.drivers.pod.virsh import (
    DOM_TEMPLATE_AMD64,
    DOM_TEMPLATE_ARM64,
    DOM_TEMPLATE_BRIDGE_INTERFACE,
    DOM_TEMPLATE_MACVLAN_INTERFACE,
    DOM_TEMPLATE_PPC64,
    DOM_TEMPLATE_S390X,
    InterfaceInfo,
    VirshPodDriver,
)
from provisioningserver.enum import LIBVIRT_NETWORK, MACVLAN_MODE_CHOICES
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils import (
    debian_to_kernel_architecture,
    kernel_to_debian_architecture,
    KERNEL_TO_DEBIAN_ARCHITECTURES,
)
from provisioningserver.utils.shell import (
    get_env_with_locale,
    has_command_available,
)
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()

SAMPLE_DOMBLKINFO = dedent(
    """
    Capacity:       21474836480
    Allocation:     5563392000
    Physical:       21478375424
    """
)

SAMPLE_DOMBLKLIST = dedent(
    """
    Type       Device     Target     Source
    ------------------------------------------------
    file       disk       vda        /var/lib/libvirt/images/example1.qcow2
    file       disk       vdb        /var/lib/libvirt/images/example2.qcow2
    file       cdrom      hdb        -
    """
)

SAMPLE_DOMINFO = dedent(
    """
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
    """
)

SAMPLE_NODEINFO = dedent(
    """
    CPU model:           x86_64
    CPU(s):              8
    CPU frequency:       2400 MHz
    CPU socket(s):       1
    Core(s) per socket:  4
    Thread(s) per core:  2
    NUMA cell(s):        1
    Memory size:         16307176 KiB
    """
)

SAMPLE_POOLLIST = dedent(
    """
     Name                 State      Autostart
    -------------------------------------------
     default              active     yes
     ubuntu               active     yes
    """
)

SAMPLE_POOLINFO = dedent(
    """
    <pool type='dir'>
        <name>default</name>
        <uuid>59edc0cb-4635-449a-80e2-2c8a59afa327</uuid>
        <capacity unit='bytes'>486362096599</capacity>
        <allocation unit='bytes'>0</allocation>
        <available unit='bytes'>486362096599</available>
        <source>
        </source>
        <target>
            <path>/var/lib/libvirt/images</path>
            <permissions>
                <mode>0711</mode>
                <owner>0</owner>
                <group>0</group>
            </permissions>
        </target>
    </pool>
    """
)

SAMPLE_POOLINFO_FULL = dedent(
    """
    <pool type='dir'>
        <name>default</name>
        <uuid>59edc0cb-4635-449a-80e2-2c8a59afa327</uuid>
        <capacity unit='bytes'>486362096599</capacity>
        <allocation unit='bytes'>486362096599</allocation>
        <available unit='bytes'>0</available>
        <source>
        </source>
        <target>
            <path>/var/lib/libvirt/images</path>
            <permissions>
                <mode>0711</mode>
                <owner>0</owner>
                <group>0</group>
            </permissions>
        </target>
    </pool>
    """
)

SAMPLE_IFLIST = dedent(
    """
    Interface  Type       Source     Model       MAC
    -------------------------------------------------------
    -          bridge     br0        e1000       %s
    -          bridge     br1        e1000       %s
    """
)

SAMPLE_NETWORK_DUMPXML = dedent(
    """
    <network>
      <name>default</name>
      <uuid>6d477dbc-c6d6-46c1-97c8-665ecab001f3</uuid>
      <forward mode='nat'>
        <nat>
          <port start='1024' end='65535'/>
        </nat>
      </forward>
      <bridge name='virbr0' stp='on' delay='0'/>
      <mac address='52:54:00:85:fc:da'/>
      <ip address='192.168.123.1' netmask='255.255.255.0'>
        <dhcp>
          <range start='192.168.123.2' end='192.168.123.254'/>
        </dhcp>
      </ip>
    </network>
    """
)

SAMPLE_NETWORK_DUMPXML_2 = dedent(
    """
    <network>
      <name>maas</name>
      <uuid>8ef77750-edb2-11e7-b8c7-b3f6673ef6b2</uuid>
      <forward mode='nat'>
        <nat>
          <port start='1024' end='65535'/>
        </nat>
      </forward>
      <bridge name='virbr1' stp='on' delay='0'/>
      <mac address='52:54:00:df:83:6c'/>
      <domain name='testnet'/>
      <ip address='172.16.99.1' netmask='255.255.255.0'>
      </ip>
    </network>
    """
)

SAMPLE_DUMPXML = dedent(
    """
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
    """
)

SAMPLE_DUMPXML_2 = dedent(
    """
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
    """
)

SAMPLE_DUMPXML_3 = dedent(
    """
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
    """
)

SAMPLE_DUMPXML_4 = dedent(
    """
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
    """
)

SAMPLE_CAPABILITY_KVM = dedent(
    """\
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
    """
)

SAMPLE_CAPABILITY_QEMU = dedent(
    """\
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
    """
)


POOLINFO_TEMPLATE = dedent(
    """
    <pool type='dir'>
        <name>{name}</name>
        <uuid>{uuid}</uuid>
        <capacity unit='bytes'>{capacity}</capacity>
        <allocation unit='bytes'>{allocation}</allocation>
        <available unit='bytes'>{available}</available>
        <source>
        </source>
        <target>
            <path>{path}</path>
            <permissions>
                <mode>0711</mode>
                <owner>0</owner>
                <group>0</group>
            </permissions>
        </target>
    </pool>
    """
)


class VirshRunFake:
    """Fake for running virtlib command.

    It can be used to patch VirshSSH.run.
    """

    def __init__(self):
        self.pools = []

    def add_pool(
        self,
        name,
        pool_type="dir",
        active=True,
        autostart=True,
        pool_uuid=None,
        capacity=None,
        allocation=None,
        available=None,
        path=None,
    ):
        if pool_uuid is None:
            pool_uuid = str(uuid4())
        if capacity is None:
            capacity = random.randint(10000000000, 1000000000000)
        if allocation is None:
            allocation = random.randint(0, capacity)
        if available is None:
            available = capacity - allocation
        if path is None:
            path = "var/lib/virtlib/" + factory.make_name("images")
        pool = {
            "name": name,
            "type": pool_type,
            "active": active,
            "autostart": autostart,
            "uuid": pool_uuid,
            "capacity": capacity,
            "allocation": allocation,
            "available": available,
            "path": path,
        }
        self.pools.append(pool)
        return pool

    def __call__(self, args):
        command = args.pop(0)
        func = getattr(self, "cmd_" + command.replace("-", "_"))
        return func(*args)

    def cmd_pool_list(self, _, pool_types):
        filter_types = pool_types.split(",")
        template = " {name: <21}{state: <11}{autostart}"
        lines = [
            template.format(name="Name", state="State", autostart="Autostart")
        ]
        lines.append("-------------------------------------------")
        lines.extend(
            template.format(
                name=pool["name"],
                state="active" if pool["active"] else "inactive",
                autostart="yes" if pool["autostart"] else "no",
            )
            for pool in self.pools
            if pool["type"] in filter_types
        )
        return "\n".join(lines)

    def cmd_pool_dumpxml(self, pool_name):
        for pool in self.pools:
            if pool["name"] == pool_name:
                break
        else:
            raise RuntimeError("No pool named " + pool_name)
        return POOLINFO_TEMPLATE.format(**pool)


def make_requested_machine():
    block_devices = [
        RequestedMachineBlockDevice(
            size=random.randint(1024**3, 4 * 1024**3)
        )
        for _ in range(3)
    ]
    interfaces = [RequestedMachineInterface() for _ in range(3)]
    return RequestedMachine(
        hostname=factory.make_name("hostname"),
        architecture="amd64/generic",
        cores=random.randint(2, 4),
        memory=random.randint(1024, 4096),
        cpu_speed=random.randint(2000, 3000),
        block_devices=block_devices,
        interfaces=interfaces,
    )


class TestVirshSSH(MAASTestCase):
    """Tests for `VirshSSH`."""

    def configure_virshssh_pexpect(self, inputs=None, dom_prefix=None):
        """Configures the VirshSSH class to use 'cat' process
        for testing instead of the actual virsh."""
        conn = virsh.VirshSSH(timeout=0.1, dom_prefix=dom_prefix)
        self.addCleanup(conn.close)
        self.patch(conn, "_execute")
        conn._spawn("cat")
        if inputs is not None:
            for line in inputs:
                conn.sendline(line)
        return conn

    def configure_virshssh(self, results, dom_prefix=None):
        virshssh = virsh.VirshSSH(dom_prefix=dom_prefix)
        mock_run = self.patch(virshssh, "run")
        if isinstance(results, str):
            mock_run.return_value = results
        else:
            # either a single exception or a list of results/errors
            mock_run.side_effect = results

        return virshssh

    def test_login_prompt(self):
        virsh_outputs = ["virsh # "]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.login(poweraddr=factory.make_name("poweraddr")))

    def test_login_with_sshkey(self):
        virsh_outputs = [
            "The authenticity of host '127.0.0.1' can't be established.",
            "ECDSA key fingerprint is "
            "00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff.",
            "Are you sure you want to continue connecting (yes/no)? ",
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_sendline = self.patch(conn, "sendline")
        conn.login(poweraddr=factory.make_name("poweraddr"))
        self.assertThat(mock_sendline, MockCalledOnceWith("yes"))

    def test_login_with_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.make_ipv4_address()
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        fake_password = factory.make_name("password")
        mock_sendline = self.patch(conn, "sendline")
        conn.login(
            poweraddr=factory.make_name("poweraddr"), password=fake_password
        )
        self.assertThat(mock_sendline, MockCalledOnceWith(fake_password))

    def test_login_missing_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.make_ipv4_address()
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, "close")
        self.assertFalse(conn.login(poweraddr=factory.make_name("poweraddr")))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_pkttyagent_permission_denied(self):
        # Sometimes pkttyagent can't be executed in the snap. The connection
        # itself still works, though.
        # See https://bugs.launchpad.net/maas/+bug/2053033
        virsh_outputs = [
            "libvirt:  error : cannot execute binary /usr/bin/pkttyagent: Permission denied",
            "Welcome to virsh, the virtualization interactive terminal.",
            "",
            "Type:  'help' for help with commands",
            "       'quit' to quit",
            "",
            "virsh # ",
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.login(poweraddr=factory.make_name("poweraddr")))

    def test_login_invalid(self):
        virsh_outputs = ["Permission denied, please try again."]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, "close")
        self.assertFalse(conn.login(poweraddr=factory.make_name("poweraddr")))
        mock_close.assert_called_once_with()

    def test_unknown(self):
        virsh_outputs = [factory.make_string()]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, "close")
        self.assertFalse(conn.login(poweraddr=factory.make_name("poweraddr")))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_login_errors_with_poweraddr_extra_parameters(self):
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        poweraddr = "qemu+ssh://ubuntu@10.0.0.2/system?no_verify=1"
        conn._spawn("cat")
        self.assertRaises(virsh.VirshError, conn.login, poweraddr)

    def test_login_with_poweraddr_adds_extra_parameters(self):
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        mock_execute = self.patch(conn, "_execute")
        mock_close = self.patch(conn, "close")
        poweraddr = "qemu+ssh://ubuntu@10.0.0.2/system"
        conn._spawn("cat")
        self.assertFalse(conn.login(poweraddr=poweraddr))
        new_poweraddr = poweraddr + "?command=/usr/lib/maas/unverified-ssh"
        self.assertThat(mock_execute, MockCalledOnceWith(new_poweraddr))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_login_with_poweraddr_no_extra_parameters(self):
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        mock_execute = self.patch(conn, "_execute")
        mock_close = self.patch(conn, "close")
        poweraddr = "qemu+ssh://ubuntu@10.0.0.2/system"
        conn._spawn("cat")
        self.assertFalse(conn.login(poweraddr=poweraddr))
        self.assertThat(
            mock_execute,
            MockCalledOnceWith(
                poweraddr + "?command=/usr/lib/maas/unverified-ssh"
            ),
        )
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_logout(self):
        conn = self.configure_virshssh_pexpect()
        mock_sendline = self.patch(conn, "sendline")
        mock_close = self.patch(conn, "close")
        conn.logout()
        self.assertThat(mock_sendline, MockCalledOnceWith("quit"))
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_prompt(self):
        virsh_outputs = ["virsh # "]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertTrue(conn.prompt())

    def test_invalid_prompt(self):
        virsh_outputs = [factory.make_string()]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        self.assertFalse(conn.prompt())

    def test_run(self):
        cmd = ["list", "--all", "--name"]
        expected = " ".join(cmd)
        names = [factory.make_name("machine") for _ in range(3)]
        conn = self.configure_virshssh_pexpect()
        conn.before = ("\n".join([expected] + names)).encode("utf-8")
        mock_sendline = self.patch(conn, "sendline")
        mock_prompt = self.patch(conn, "prompt")
        output = conn.run(cmd)
        self.assertThat(mock_sendline, MockCalledOnceWith(expected))
        self.assertThat(mock_prompt, MockCalledOnceWith())
        self.assertEqual("\n".join(names), output)

    def test_run_error(self):
        cmd = ["list", "--all", "--name"]
        message = "something failed"
        conn = self.configure_virshssh_pexpect()
        conn.before = "\n".join([" ".join(cmd), f"error: {message}"]).encode(
            "utf-8"
        )
        self.patch(conn, "sendline")
        self.patch(conn, "prompt")
        mock_maaslog = self.patch(virsh, "maaslog")
        error = self.assertRaises(virsh.VirshError, conn.run, cmd)
        expected_message = "Virsh command ['list', '--all', '--name'] failed: something failed"
        self.assertEqual(str(error), expected_message)
        mock_maaslog.error.assert_called_once_with(expected_message)

    def test_get_column_values(self):
        keys = ["Source", "Model"]
        expected = (("br0", "e1000"), ("br1", "e1000"))
        conn = self.configure_virshssh("")
        values = conn._get_column_values(SAMPLE_IFLIST, keys)
        self.assertEqual(values, expected)

    def test_get_key_value(self):
        key = "CPU model"
        expected = "x86_64"
        conn = self.configure_virshssh("")
        value = conn.get_key_value(SAMPLE_NODEINFO, key)
        self.assertEqual(value, expected)

    def test_create_storage_pool(self):
        conn = self.configure_virshssh("")
        conn.create_storage_pool()
        conn.run.assert_has_calls(
            [
                call(
                    [
                        "pool-define-as",
                        "maas",
                        "dir",
                        "- - - -",
                        "/var/lib/libvirt/maas-images",
                    ]
                ),
                call(["pool-build", "maas"]),
                call(["pool-start", "maas"]),
                call(["pool-autostart", "maas"]),
            ],
        )

    def test_list_machines(self):
        names = [factory.make_name("machine") for _ in range(3)]
        conn = self.configure_virshssh("\n".join(names))
        expected = conn.list_machines()
        self.assertEqual(names, expected)

    def test_list_machines_with_dom_prefix(self):
        prefix = "dom_prefix"
        names = [prefix + factory.make_name("machine") for _ in range(3)]
        conn = self.configure_virshssh("\n".join(names), dom_prefix=prefix)
        expected = conn.list_machines()
        self.assertEqual(names, expected)

    def test_list_pools(self):
        names = ["default", "ubuntu"]
        conn = self.configure_virshssh(SAMPLE_POOLLIST)
        expected = conn.list_pools()
        self.assertEqual(names, expected)

    def test_list_machine_block_devices(self):
        block_devices = [
            ("vda", "/var/lib/libvirt/images/example1.qcow2"),
            ("vdb", "/var/lib/libvirt/images/example2.qcow2"),
        ]
        conn = self.configure_virshssh(SAMPLE_DOMBLKLIST)
        expected = conn.list_machine_block_devices(
            factory.make_name("machine")
        )
        self.assertEqual(block_devices, expected)

    def test_get_machine_state(self):
        state = factory.make_name("state")
        conn = self.configure_virshssh(state)
        expected = conn.get_machine_state("")
        self.assertEqual(state, expected)

    def test_get_machine_state_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.get_machine_state("")
        self.assertIsNone(expected)

    def test_machine_mac_addresses_returns_list(self):
        macs = [factory.make_mac_address() for _ in range(2)]
        output = SAMPLE_IFLIST % (macs[0], macs[1])
        conn = self.configure_virshssh(output)
        expected = conn.get_machine_interface_info("")
        self.assertEqual(
            [
                InterfaceInfo("bridge", "br0", "e1000", macs[0]),
                InterfaceInfo("bridge", "br1", "e1000", macs[1]),
            ],
            expected,
        )

    def test_get_machine_interface_info_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.get_machine_state("")
        self.assertIsNone(expected)

    def test_get_pod_cpu_count(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_cpu_count(nodeinfo)
        self.assertEqual(8, expected)

    def test_get_pod_cpu_count_returns_zero_if_info_not_available(self):
        conn = self.configure_virshssh("")
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_cpu_count(nodeinfo)
        self.assertEqual(0, expected)

    def test_get_machine_cpu_count(self):
        conn = self.configure_virshssh(SAMPLE_DOMINFO)
        expected = conn.get_machine_cpu_count(factory.make_name("machine"))
        self.assertEqual(1, expected)

    def test_get_machine_cpu_count_returns_zero_if_info_not_available(self):
        conn = self.configure_virshssh("")
        expected = conn.get_machine_cpu_count(factory.make_name("machine"))
        self.assertEqual(0, expected)

    def test_get_pod_cpu_speed(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_cpu_speed(nodeinfo)
        self.assertEqual(2400, expected)

    def test_get_pod_cpu_speed_returns_zero_if_info_not_available(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        mock_get_key_value_unitless = self.patch(
            virsh.VirshSSH, "get_key_value_unitless"
        )
        mock_get_key_value_unitless.return_value = None
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_cpu_speed(nodeinfo)
        self.assertEqual(0, expected)

    def test_get_pod_memory(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_memory(nodeinfo)
        self.assertEqual(int(16307176 / 1024), expected)

    def test_get_pod_memory_returns_zero_if_info_not_available(self):
        conn = self.configure_virshssh("")
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_memory(nodeinfo)
        self.assertEqual(0, expected)

    def test_get_machine_memory(self):
        conn = self.configure_virshssh(SAMPLE_DOMINFO)
        expected = conn.get_machine_memory(factory.make_name("machine"))
        self.assertEqual(int(1048576 / 1024), expected)

    def test_get_machine_memory_returns_zero_if_info_not_available(self):
        conn = self.configure_virshssh("")
        expected = conn.get_machine_memory(factory.make_name("machine"))
        self.assertEqual(0, expected)

    def test_get_pod_storage_pools(self):
        conn = virsh.VirshSSH()
        fake_runner = VirshRunFake()
        [fake_runner.add_pool(factory.make_name("pool")) for _ in range(3)]
        run_mock = self.patch(virsh.VirshSSH, "run")
        run_mock.side_effect = fake_runner
        expected = [
            DiscoveredPodStoragePool(
                id=pool["uuid"],
                type="dir",
                name=pool["name"],
                storage=pool["capacity"],
                path=pool["path"],
            )
            for pool in fake_runner.pools
        ]
        self.assertEqual(expected, conn.get_pod_storage_pools())

    def test_get_pod_storage_pools_filters_supported(self):
        conn = virsh.VirshSSH()
        fake_runner = VirshRunFake()
        valid_pools = [
            fake_runner.add_pool(factory.make_name("pool")) for _ in range(3)
        ]
        # extra pool of unsupported type is not returned
        fake_runner.add_pool(factory.make_name("pool"), pool_type="disk")
        self.patch(virsh.VirshSSH, "run").side_effect = fake_runner
        self.assertEqual(
            conn.get_pod_storage_pools(),
            [
                DiscoveredPodStoragePool(
                    id=pool["uuid"],
                    type="dir",
                    name=pool["name"],
                    storage=pool["capacity"],
                    path=pool["path"],
                )
                for pool in valid_pools
            ],
        )

    def test_get_pod_storage_pools_no_pool(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO)
        pools_mock = self.patch(virsh.VirshSSH, "list_pools")
        pools_mock.return_value = []
        self.assertEqual([], conn.get_pod_storage_pools())

    def test_get_pod_available_local_storage(self):
        conn = self.configure_virshssh(SAMPLE_POOLINFO)
        pools_mock = self.patch(virsh.VirshSSH, "list_pools")
        pools_mock.return_value = [factory.make_name("pool") for _ in range(3)]
        expected = conn.get_pod_available_local_storage()
        self.assertEqual(int(452.96 * 3 * 2**30), expected)

    def test_get_machine_local_storage(self):
        conn = self.configure_virshssh(SAMPLE_DOMBLKINFO)
        expected = conn.get_machine_local_storage(
            factory.make_name("machine"), factory.make_name("device")
        )
        self.assertEqual(21474836480, expected)

    def test_get_machine_local_storage_handles_no_output(self):
        conn = self.configure_virshssh("")
        expected = conn.get_machine_local_storage(
            factory.make_name("machine"), factory.make_name("device")
        )
        self.assertIsNone(expected)

    def test_get_pod_arch(self):
        conn = self.configure_virshssh(SAMPLE_NODEINFO)
        nodeinfo = conn.get_pod_nodeinfo()
        expected = conn.get_pod_arch(nodeinfo)
        self.assertEqual("amd64/generic", expected)

    def test_get_pod_arch_raises_error_if_not_found(self):
        conn = self.configure_virshssh("")
        self.assertRaises(PodInvalidResources, conn.get_pod_arch, None)

    def test_get_machine_arch_returns_valid_debian_architecture(self):
        arch = random.choice(list(KERNEL_TO_DEBIAN_ARCHITECTURES.keys()))
        fixed_arch = kernel_to_debian_architecture(arch)
        output = SAMPLE_DUMPXML % arch
        conn = self.configure_virshssh(output)
        expected = conn.get_machine_arch("")
        self.assertEqual(fixed_arch, expected)

    def test_get_pod_resources(self):
        conn = self.configure_virshssh("")
        architecture = factory.make_name("arch")
        cores = random.randint(1, 8)
        cpu_speed = random.randint(1000, 2000)
        memory = random.randint(4096, 8192)
        storage_pools = [
            DiscoveredPodStoragePool(
                id=factory.make_name("uuid"),
                type="dir",
                name=factory.make_name("pool"),
                storage=random.randint(4096, 8192),
                path="/var/lib/libvirt/images",
            )
            for _ in range(3)
        ]
        local_storage = sum(pool.storage for pool in storage_pools)
        mock_get_pod_nodeinfo = self.patch(virsh.VirshSSH, "get_pod_nodeinfo")
        mock_get_pod_arch = self.patch(virsh.VirshSSH, "get_pod_arch")
        mock_get_pod_cpu_count = self.patch(
            virsh.VirshSSH, "get_pod_cpu_count"
        )
        mock_get_pod_cpu_speed = self.patch(
            virsh.VirshSSH, "get_pod_cpu_speed"
        )
        mock_get_pod_memory = self.patch(virsh.VirshSSH, "get_pod_memory")
        mock_get_pod_storage_pools = self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        )
        mock_get_pod_server_version = self.patch(
            virsh.VirshSSH, "get_server_version"
        )
        mock_get_pod_nodeinfo.return_value = SAMPLE_NODEINFO
        mock_get_pod_arch.return_value = architecture
        mock_get_pod_cpu_count.return_value = cores
        mock_get_pod_cpu_speed.return_value = cpu_speed
        mock_get_pod_memory.return_value = memory
        mock_get_pod_storage_pools.return_value = storage_pools
        mock_get_pod_server_version.return_value = "6.0.0"

        discovered_pod = conn.get_pod_resources()
        self.assertEqual([architecture], discovered_pod.architectures)
        self.assertEqual(
            [
                Capabilities.COMPOSABLE,
                Capabilities.DYNAMIC_LOCAL_STORAGE,
                Capabilities.OVER_COMMIT,
                Capabilities.STORAGE_POOLS,
            ],
            discovered_pod.capabilities,
        )
        self.assertEqual(cores, discovered_pod.cores)
        self.assertEqual(cpu_speed, discovered_pod.cpu_speed)
        self.assertEqual(memory, discovered_pod.memory)
        self.assertEqual(storage_pools, discovered_pod.storage_pools)
        self.assertEqual(local_storage, discovered_pod.local_storage)
        self.assertEqual(discovered_pod.version, "6.0.0")

    def test_get_server_version(self):
        conn = self.configure_virshssh(
            dedent(
                """\
            Compiled against library: libvirt 6.6.0
            Using library: libvirt 6.6.0
            Using API: QEMU 6.6.0
            Running hypervisor: QEMU 5.0.0
            Running against daemon: 6.6.0

            """
            )
        )
        version = conn.get_server_version()
        conn.run.assert_called_with(["version", "--daemon"])
        self.assertEqual(version, "6.6.0")

    def test_get_pod_hints(self):
        conn = self.configure_virshssh("")
        cores = random.randint(8, 16)
        memory = random.randint(4096, 8192)
        cpu_speed = random.randint(2000, 3000)
        local_storage = random.randint(4096, 8192)
        mock_get_pod_nodeinfo = self.patch(virsh.VirshSSH, "get_pod_nodeinfo")
        mock_get_pod_cores = self.patch(virsh.VirshSSH, "get_pod_cpu_count")
        mock_get_pod_cores.return_value = cores
        mock_get_pod_memory = self.patch(virsh.VirshSSH, "get_pod_memory")
        mock_get_pod_nodeinfo.return_value = SAMPLE_NODEINFO
        mock_get_pod_memory.return_value = memory
        mock_get_pod_cpu_speed = self.patch(
            virsh.VirshSSH, "get_pod_cpu_speed"
        )
        mock_get_pod_cpu_speed.return_value = cpu_speed
        mock_get_pod_available_local_storage = self.patch(
            virsh.VirshSSH, "get_pod_available_local_storage"
        )
        mock_get_pod_available_local_storage.return_value = local_storage

        discovered_pod_hints = conn.get_pod_hints()
        self.assertEqual(cores, discovered_pod_hints.cores)
        self.assertEqual(memory, discovered_pod_hints.memory)
        self.assertEqual(cpu_speed, discovered_pod_hints.cpu_speed)
        self.assertEqual(local_storage, discovered_pod_hints.local_storage)

    def test_get_discovered_machine(self):
        conn = self.configure_virshssh("")
        hostname = factory.make_name("hostname")
        architecture = factory.make_name("arch")
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)
        storage_pool_names = [factory.make_name("storage") for _ in range(3)]
        storage_pools = [
            DiscoveredPodStoragePool(
                id=factory.make_name("uuid"),
                type="dir",
                name=name,
                storage=random.randint(4096, 8192),
                path="/var/lib/libvirt/%s/" % name,
            )
            for name in storage_pool_names
        ]
        device_names = [factory.make_name("device") for _ in range(3)]
        devices = []
        for name in device_names:
            pool = random.choice(storage_pools)
            name = factory.make_name("device")
            devices.append((name, pool.path + "/" + name))
        device_tags = [
            [factory.make_name("tag") for _ in range(3)] for _ in range(3)
        ]
        local_storage = [random.randint(4096, 8192) for _ in range(3)]
        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        mock_get_pod_storage_pools = self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        )
        mock_get_machine_arch = self.patch(virsh.VirshSSH, "get_machine_arch")
        mock_get_machine_cpu_count = self.patch(
            virsh.VirshSSH, "get_machine_cpu_count"
        )
        mock_get_machine_memory = self.patch(
            virsh.VirshSSH, "get_machine_memory"
        )
        mock_get_machine_state = self.patch(
            virsh.VirshSSH, "get_machine_state"
        )
        mock_list_machine_block_devices = self.patch(
            virsh.VirshSSH, "list_machine_block_devices"
        )
        mock_get_machine_local_storage = self.patch(
            virsh.VirshSSH, "get_machine_local_storage"
        )
        mock_get_machine_interface_info = self.patch(
            virsh.VirshSSH, "get_machine_interface_info"
        )
        mock_get_pod_storage_pools.return_value = storage_pools
        mock_get_machine_arch.return_value = architecture
        mock_get_machine_cpu_count.return_value = cores
        mock_get_machine_memory.return_value = memory
        mock_get_machine_state.return_value = "shut off"
        mock_list_machine_block_devices.return_value = devices
        mock_get_machine_local_storage.side_effect = local_storage
        mock_get_machine_interface_info.return_value = [
            InterfaceInfo("bridge", "br0", "virtio", mac)
            for mac in mac_addresses
        ]

        block_devices = [
            RequestedMachineBlockDevice(
                size=local_storage[idx], tags=device_tags[idx]
            )
            for idx in range(3)
        ]
        # None of the parameters matter in the RequestedMachine except for
        # block_device. All other paramters are ignored by this method.
        request = RequestedMachine(
            hostname=None,
            architecture="",
            cores=0,
            memory=0,
            interfaces=[],
            block_devices=block_devices,
        )
        discovered_machine = conn.get_discovered_machine(
            hostname, request=request
        )
        self.assertEqual(hostname, discovered_machine.hostname)
        self.assertEqual(architecture, discovered_machine.architecture)
        self.assertEqual(cores, discovered_machine.cores)
        self.assertEqual(memory, discovered_machine.memory)
        self.assertCountEqual(
            local_storage, [bd.size for bd in discovered_machine.block_devices]
        )
        self.assertEqual(
            device_tags, [bd.tags for bd in discovered_machine.block_devices]
        )
        self.assertCountEqual(
            mac_addresses,
            [m.mac_address for m in discovered_machine.interfaces],
        )
        self.assertTrue(discovered_machine.interfaces[0].boot)
        self.assertFalse(discovered_machine.interfaces[1].boot)
        self.assertFalse(discovered_machine.interfaces[2].boot)

    def test_get_discovered_machine_handles_no_storage_pools_found(self):
        conn = self.configure_virshssh("")
        hostname = factory.make_name("hostname")
        architecture = factory.make_name("arch")
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)

        # Storage pool names and pools are only for setting the devices.
        # Further down we will be setting the return value for
        # find_storage_pool to None which happens if a storage pool
        # cannot be found for a specific block device.
        storage_pool_names = [factory.make_name("storage") for _ in range(3)]
        storage_pools = [
            DiscoveredPodStoragePool(
                id=factory.make_name("uuid"),
                type="dir",
                name=name,
                storage=random.randint(4096, 8192),
                path="/var/lib/libvirt/%s/" % name,
            )
            for name in storage_pool_names
        ]
        device_names = [factory.make_name("device") for _ in range(3)]
        devices = []
        for name in device_names:
            pool = random.choice(storage_pools)
            name = factory.make_name("device")
            devices.append((name, pool.path + "/" + name))
        device_tags = [
            [factory.make_name("tag") for _ in range(3)] for _ in range(3)
        ]
        local_storage = [random.randint(4096, 8192) for _ in range(3)]
        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        mock_get_pod_storage_pools = self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        )
        mock_find_storage_pool = self.patch(
            virsh.VirshSSH, "find_storage_pool"
        )
        mock_get_machine_arch = self.patch(virsh.VirshSSH, "get_machine_arch")
        mock_get_machine_cpu_count = self.patch(
            virsh.VirshSSH, "get_machine_cpu_count"
        )
        mock_get_machine_memory = self.patch(
            virsh.VirshSSH, "get_machine_memory"
        )
        mock_get_machine_state = self.patch(
            virsh.VirshSSH, "get_machine_state"
        )
        mock_list_machine_block_devices = self.patch(
            virsh.VirshSSH, "list_machine_block_devices"
        )
        mock_get_machine_local_storage = self.patch(
            virsh.VirshSSH, "get_machine_local_storage"
        )
        mock_get_machine_interface_info = self.patch(
            virsh.VirshSSH, "get_machine_interface_info"
        )
        mock_get_pod_storage_pools.return_value = storage_pools
        mock_find_storage_pool.return_value = None
        mock_get_machine_arch.return_value = architecture
        mock_get_machine_cpu_count.return_value = cores
        mock_get_machine_memory.return_value = memory
        mock_get_machine_state.return_value = "shut off"
        mock_list_machine_block_devices.return_value = devices
        mock_get_machine_local_storage.side_effect = local_storage
        mock_get_machine_interface_info.return_value = [
            InterfaceInfo("bridge", "br0", "virtio", mac)
            for mac in mac_addresses
        ]

        block_devices = [
            RequestedMachineBlockDevice(
                size=local_storage[idx], tags=device_tags[idx]
            )
            for idx in range(3)
        ]
        # None of the parameters matter in the RequestedMachine except for
        # block_device. All other paramters are ignored by this method.
        request = RequestedMachine(
            hostname=None,
            architecture="",
            cores=0,
            memory=0,
            interfaces=[],
            block_devices=block_devices,
        )
        discovered_machine = conn.get_discovered_machine(
            hostname, request=request
        )
        self.assertEqual(hostname, discovered_machine.hostname)
        self.assertEqual(architecture, discovered_machine.architecture)
        self.assertEqual(cores, discovered_machine.cores)
        self.assertEqual(memory, discovered_machine.memory)
        self.assertCountEqual(
            local_storage, [bd.size for bd in discovered_machine.block_devices]
        )
        self.assertCountEqual(
            device_tags, [bd.tags for bd in discovered_machine.block_devices]
        )
        self.assertCountEqual(
            mac_addresses,
            [m.mac_address for m in discovered_machine.interfaces],
        )
        self.assertTrue(discovered_machine.interfaces[0].boot)
        self.assertFalse(discovered_machine.interfaces[1].boot)
        self.assertFalse(discovered_machine.interfaces[2].boot)

    def test_get_discovered_machine_handles_bad_storage_device(self):
        conn = self.configure_virshssh("")
        hostname = factory.make_name("hostname")
        architecture = factory.make_name("arch")
        cores = random.randint(1, 8)
        memory = random.randint(4096, 8192)
        storage_pool_names = [factory.make_name("storage") for _ in range(3)]
        storage_pools = [
            DiscoveredPodStoragePool(
                id=factory.make_name("uuid"),
                type="dir",
                name=name,
                storage=random.randint(4096, 8192),
                path="/var/lib/libvirt/%s/" % name,
            )
            for name in storage_pool_names
        ]
        device_names = [factory.make_name("device") for _ in range(3)]
        devices = []
        for name in device_names:
            pool = random.choice(storage_pools)
            name = factory.make_name("device")
            devices.append((name, pool.path + "/" + name))
        local_storage = [random.randint(4096, 8192) for _ in range(2)] + [
            None
        ]  # Last storage device is bad.
        mac_addresses = [factory.make_mac_address() for _ in range(3)]
        mock_get_pod_storage_pools = self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        )
        mock_get_machine_arch = self.patch(virsh.VirshSSH, "get_machine_arch")
        mock_get_machine_cpu_count = self.patch(
            virsh.VirshSSH, "get_machine_cpu_count"
        )
        mock_get_machine_memory = self.patch(
            virsh.VirshSSH, "get_machine_memory"
        )
        mock_get_machine_state = self.patch(
            virsh.VirshSSH, "get_machine_state"
        )
        mock_list_machine_block_devices = self.patch(
            virsh.VirshSSH, "list_machine_block_devices"
        )
        mock_get_machine_local_storage = self.patch(
            virsh.VirshSSH, "get_machine_local_storage"
        )
        mock_get_machine_interface_info = self.patch(
            virsh.VirshSSH, "get_machine_interface_info"
        )
        mock_get_pod_storage_pools.return_value = storage_pools
        mock_get_machine_arch.return_value = architecture
        mock_get_machine_cpu_count.return_value = cores
        mock_get_machine_memory.return_value = memory
        mock_get_machine_state.return_value = "shut off"
        mock_list_machine_block_devices.return_value = devices
        mock_get_machine_local_storage.side_effect = local_storage
        mock_get_machine_interface_info.return_value = mac_addresses

        discovered_machine = conn.get_discovered_machine(hostname)
        self.assertIsNone(discovered_machine)

    def test_check_machine_can_startup(self):
        machine = factory.make_name("machine")
        conn = self.configure_virshssh("")
        conn.check_machine_can_startup(machine)
        conn.run.assert_has_calls(
            [
                call(["start", "--paused", machine]),
                call(["destroy", machine]),
            ]
        )

    def test_check_machine_can_startup_raises_exception(self):
        machine = factory.make_name("machine")
        conn = self.configure_virshssh([virsh.VirshError("some error"), ""])
        mock_delete_domain = self.patch(virsh.VirshSSH, "delete_domain")
        self.assertRaises(
            virsh.VirshError, conn.check_machine_can_startup, machine
        )
        mock_delete_domain.assert_called_once_with(machine)
        conn.run.assert_called_once_with(["start", "--paused", machine])

    def test_set_machine_autostart(self):
        conn = self.configure_virshssh("")
        expected = conn.set_machine_autostart(factory.make_name("machine"))
        self.assertTrue(expected)

    def test_set_machine_autostart_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.poweron(factory.make_name("machine"))
        self.assertFalse(expected)

    def test_configure_pxe_boot(self):
        conn = self.configure_virshssh("")
        mock_get_machine_xml = self.patch(virsh.VirshSSH, "get_machine_xml")
        mock_get_machine_xml.return_value = SAMPLE_DUMPXML
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        conn.configure_pxe_boot(factory.make_name("machine"))

        self.assertThat(NamedTemporaryFile, MockCalledOnceWith())
        self.assertThat(tmpfile.__enter__, MockCalledOnceWith())
        self.assertIn(
            b'boot dev="network"',
            tmpfile.write.call_args_list[0][0][0],
        )
        self.assertThat(tmpfile.flush, MockCalledOnceWith())
        self.assertThat(tmpfile.__exit__, MockCalledOnceWith(None, None, None))

    def test_configure_pxe_boot_true_for_xml_with_netboot_already_set(self):
        conn = self.configure_virshssh("")
        mock_get_machine_xml = self.patch(virsh.VirshSSH, "get_machine_xml")
        mock_get_machine_xml.return_value = SAMPLE_DUMPXML_2
        expected = conn.configure_pxe_boot(factory.make_name("machine"))
        self.assertTrue(expected)

    def test_configure_pxe_boot_false_no_xml(self):
        conn = self.configure_virshssh("")
        mock_get_machine_xml = self.patch(virsh.VirshSSH, "get_machine_xml")
        mock_get_machine_xml.return_value = None
        expected = conn.configure_pxe_boot(factory.make_name("machine"))
        self.assertFalse(expected)

    def test_poweron(self):
        conn = self.configure_virshssh("")
        expected = conn.poweron(factory.make_name("machine"))
        self.assertTrue(expected)

    def test_poweron_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.poweron(factory.make_name("machine"))
        self.assertFalse(expected)

    def test_poweroff(self):
        conn = self.configure_virshssh("")
        expected = conn.poweroff(factory.make_name("machine"))
        self.assertTrue(expected)

    def test_poweroff_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        expected = conn.poweroff(factory.make_name("machine"))
        self.assertFalse(expected)

    def test_resets_locale(self):
        """
        VirshSSH resets the locale to ensure we only ever get English strings.
        """
        c_utf8_environment = get_env_with_locale()
        mock_spawn = self.patch(pexpect.spawn, "__init__")
        self.configure_virshssh("")
        self.assertThat(
            mock_spawn,
            MockCalledOnceWith(
                None, timeout=30, maxread=2000, env=c_utf8_environment
            ),
        )

    def test_get_usable_pool(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        disk = RequestedMachineBlockDevice(
            size=random.randint(
                pools[0].available + 1, pools[1].available - 1
            ),
            tags=[],
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertEqual(
            (pools[1].type, pools[1].name), conn.get_usable_pool(disk)
        )

    def test_get_usable_pool_filters_on_disk_tags(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        selected_pool = random.choice(pools)
        disk = RequestedMachineBlockDevice(
            size=selected_pool.available, tags=[selected_pool.name]
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertEqual(
            (selected_pool.type, selected_pool.name),
            conn.get_usable_pool(disk),
        )

    def test_get_usable_pool_filters_on_disk_tags_raises_invalid(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        selected_pool = random.choice(pools)
        disk = RequestedMachineBlockDevice(
            size=selected_pool.available + 1, tags=[selected_pool.name]
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertRaises(PodInvalidResources, conn.get_usable_pool, disk)

    def test_get_usable_pool_filters_on_default_pool_id(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        selected_pool = random.choice(pools)
        disk = RequestedMachineBlockDevice(
            size=selected_pool.available, tags=[]
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertEqual(
            (selected_pool.type, selected_pool.name),
            conn.get_usable_pool(disk, selected_pool.id),
        )

    def test_get_usable_pool_filters_on_default_pool_id_raises_invalid(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        selected_pool = random.choice(pools)
        disk = RequestedMachineBlockDevice(
            size=selected_pool.available + 1, tags=[]
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertRaises(
            PodInvalidResources, conn.get_usable_pool, disk, selected_pool.id
        )

    def test_get_usable_pool_filters_on_default_pool_name(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        selected_pool = random.choice(pools)
        disk = RequestedMachineBlockDevice(
            size=selected_pool.available, tags=[]
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertEqual(
            (selected_pool.type, selected_pool.name),
            conn.get_usable_pool(disk, selected_pool.name),
        )

    def test_get_usable_pool_filters_on_default_pool_name_raises_invalid(self):
        conn = self.configure_virshssh("")
        pools = []
        for i in range(3):
            pool = DiscoveredPodStoragePool(
                id=factory.make_name("id"),
                name=factory.make_name("pool"),
                path="/var/lib/libvirt/images",
                type="dir",
                storage=random.randint(i * 1000, (i + 1) * 1000),
            )
            setattr(pool, "available", pool.storage)
            pools.append(pool)
        selected_pool = random.choice(pools)
        disk = RequestedMachineBlockDevice(
            size=selected_pool.available + 1, tags=[]
        )
        self.patch(
            virsh.VirshSSH, "get_pod_storage_pools"
        ).return_value = pools
        self.assertRaises(
            PodInvalidResources, conn.get_usable_pool, disk, selected_pool.name
        )

    def test_create_local_volume_returns_None(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_usable_pool").return_value = (
            None,
            None,
        )
        self.assertIsNone(
            conn._create_local_volume(random.randint(1000, 2000))
        )

    def test_create_local_volume_returns_tagged_pool_and_volume(self):
        tagged_pools = ["pool1", "pool2"]
        conn = self.configure_virshssh(
            (SAMPLE_POOLINFO_FULL, SAMPLE_POOLINFO, None)
        )
        self.patch(conn, "list_pools").return_value = tagged_pools
        disk = RequestedMachineBlockDevice(size=4096, tags=tagged_pools)
        used_pool, _ = conn._create_local_volume(disk)
        self.assertEqual(tagged_pools[1], used_pool)

    def test_create_local_volume_makes_call_returns_pool_and_volume_dir(self):
        conn = self.configure_virshssh("")
        pool = factory.make_name("pool")
        self.patch(virsh.VirshSSH, "get_usable_pool").return_value = (
            "dir",
            pool,
        )
        disk = RequestedMachineBlockDevice(
            size=random.randint(1000, 2000), tags=[]
        )
        used_pool, volume_name = conn._create_local_volume(disk)
        conn.run.assert_called_once_with(
            [
                "vol-create-as",
                used_pool,
                volume_name,
                str(disk.size),
                "--allocation",
                "0",
                "--format",
                "raw",
            ]
        )
        self.assertEqual(pool, used_pool)
        self.assertIsNotNone(volume_name)

    def test_create_local_volume_makes_call_returns_pool_and_volume_lvm(self):
        conn = self.configure_virshssh("")
        pool = factory.make_name("pool")
        self.patch(virsh.VirshSSH, "get_usable_pool").return_value = (
            "logical",
            pool,
        )
        disk = RequestedMachineBlockDevice(
            size=random.randint(1000, 2000), tags=[]
        )
        used_pool, volume_name = conn._create_local_volume(disk)
        conn.run.assert_called_once_with(
            [
                "vol-create-as",
                used_pool,
                volume_name,
                str(disk.size),
            ]
        )
        self.assertEqual(pool, used_pool)
        self.assertIsNotNone(volume_name)

    def test_create_local_volume_makes_call_returns_pool_and_volume_zfs(self):
        conn = self.configure_virshssh("")
        pool = factory.make_name("pool")
        self.patch(virsh.VirshSSH, "get_usable_pool").return_value = (
            "zfs",
            pool,
        )
        disk = RequestedMachineBlockDevice(
            size=random.randint(1000, 2000), tags=[]
        )
        used_pool, volume_name = conn._create_local_volume(disk)
        size = int(floor(disk.size / 2**20)) * 2**20
        conn.run.assert_called_once_with(
            [
                "vol-create-as",
                used_pool,
                volume_name,
                str(size),
                "--allocation",
                "0",
            ]
        )
        self.assertEqual(pool, used_pool)
        self.assertIsNotNone(volume_name)

    def test_delete_local_volume(self):
        conn = self.configure_virshssh("")
        pool = factory.make_name("pool")
        volume_name = factory.make_name("volume")
        conn.delete_local_volume(pool, volume_name)
        conn.run.assert_called_once_with(
            ["vol-delete", volume_name, "--pool", pool]
        )

    def test_get_volume_path(self):
        pool = factory.make_name("pool")
        volume_name = factory.make_name("volume")
        volume_path = factory.make_name("path")
        conn = self.configure_virshssh(volume_path)
        self.assertEqual(volume_path, conn.get_volume_path(pool, volume_name))
        conn.run.assert_called_once_with(
            ["vol-path", volume_name, "--pool", pool]
        )

    def test_attach_local_volume(self):
        conn = self.configure_virshssh("")
        domain = factory.make_name("domain")
        pool = factory.make_name("pool")
        volume_name = factory.make_name("volume")
        volume_path = factory.make_name("/some/path/to_vol_serial")
        serial = os.path.basename(volume_path)
        device_name = factory.make_name("device")
        self.patch(
            virsh.VirshSSH, "get_volume_path"
        ).return_value = volume_path
        conn.attach_local_volume(domain, pool, volume_name, device_name)
        conn.run.assert_called_once_with(
            [
                "attach-disk",
                domain,
                volume_path,
                device_name,
                "--targetbus",
                "virtio",
                "--sourcetype",
                "file",
                "--config",
                "--serial",
                serial,
            ]
        )

    def test_get_networks_list(self):
        networks = [factory.make_name("network") for _ in range(3)]
        conn = self.configure_virshssh("\n".join(networks))
        self.assertEqual(networks, conn.get_network_list())

    def test_check_network_maas_dhcp_enabled_returns_None_virsh_dhcp(self):
        bridge = "virbr0"
        conn = self.configure_virshssh("")
        host_interfaces = {factory.make_name("ifname"): False, bridge: True}
        mock_get_network_xml = self.patch(virsh.VirshSSH, "get_network_xml")
        mock_get_network_xml.return_value = SAMPLE_NETWORK_DUMPXML
        expected = conn.check_network_maas_dhcp_enabled(
            bridge, host_interfaces
        )
        self.assertIsNone(expected)

    def test_check_network_maas_dhcp_enabled_returns_network(self):
        bridge = "virbr1"
        conn = self.configure_virshssh("")
        host_interfaces = {factory.make_name("ifname"): False, bridge: True}
        mock_get_network_xml = self.patch(virsh.VirshSSH, "get_network_xml")
        mock_get_network_xml.return_value = SAMPLE_NETWORK_DUMPXML_2
        bridge_name = conn.check_network_maas_dhcp_enabled(
            bridge, host_interfaces
        )
        self.assertEqual(bridge_name, bridge)

    def test_get_default_interface_attachment_no_host_interfaces_maas(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            LIBVIRT_NETWORK.MAAS,
            LIBVIRT_NETWORK.DEFAULT,
            "other",
        ]
        network, attach_type = conn.get_default_interface_attachment([])
        self.assertEqual(LIBVIRT_NETWORK.MAAS, network)
        self.assertEqual(InterfaceAttachType.NETWORK, attach_type)

    def test_get_default_interface_attachment_no_host_interfaces_default(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            LIBVIRT_NETWORK.DEFAULT,
            "other",
        ]
        network, attach_type = conn.get_default_interface_attachment([])
        self.assertEqual(LIBVIRT_NETWORK.DEFAULT, network)
        self.assertEqual(InterfaceAttachType.NETWORK, attach_type)

    def test_get_default_interface_attachment_errors_no_nics_or_networks(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = []
        self.assertRaises(
            PodInvalidResources, conn.get_default_interface_attachment, None
        )

    def test_get_default_interface_attachment_maas_bridge_no_virsh_dhcp(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            LIBVIRT_NETWORK.MAAS,
            LIBVIRT_NETWORK.DEFAULT,
            "other",
        ]
        self.patch(
            virsh.VirshSSH, "check_network_maas_dhcp_enabled"
        ).return_value = "virbr0"
        host_interfaces = [
            KnownHostInterface(
                ifname=LIBVIRT_NETWORK.MAAS,
                attach_type=InterfaceAttachType.NETWORK,
                dhcp_enabled=True,
            )
        ]
        network, attach_type = conn.get_default_interface_attachment(
            host_interfaces
        )
        # This shows us that the method returned with these values.
        self.assertEqual(LIBVIRT_NETWORK.MAAS, network)
        self.assertEqual(InterfaceAttachType.NETWORK, attach_type)

    def test_get_default_interface_attachment_default_brd_no_virsh_dhcp(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            LIBVIRT_NETWORK.DEFAULT,
            "other",
        ]
        self.patch(
            virsh.VirshSSH, "check_network_maas_dhcp_enabled"
        ).return_value = "virbr1"
        host_interfaces = [
            KnownHostInterface(
                ifname=LIBVIRT_NETWORK.DEFAULT,
                attach_type=InterfaceAttachType.NETWORK,
                dhcp_enabled=True,
            )
        ]
        network, attach_type = conn.get_default_interface_attachment(
            host_interfaces
        )
        # This shows us that the method returned with these values.
        self.assertEqual(LIBVIRT_NETWORK.DEFAULT, network)
        self.assertEqual(InterfaceAttachType.NETWORK, attach_type)

    def test_get_default_interface_attachment_vlan_bridge_no_virsh_dhcp(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            LIBVIRT_NETWORK.MAAS,
            LIBVIRT_NETWORK.DEFAULT,
            "other",
        ]
        self.patch(
            virsh.VirshSSH, "check_network_maas_dhcp_enabled"
        ).side_effect = (None, None, "br0")
        host_interfaces = [
            KnownHostInterface(
                ifname="br0",
                attach_type=InterfaceAttachType.BRIDGE,
                dhcp_enabled=True,
            )
        ]
        ifname, attach_type = conn.get_default_interface_attachment(
            host_interfaces
        )
        # This shows us that the method returned with these values.
        self.assertEqual("br0", ifname)
        self.assertEqual(InterfaceAttachType.BRIDGE, attach_type)

    def test_get_default_interface_attachment_macvlan_no_virsh_dhcp(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = [
            LIBVIRT_NETWORK.MAAS,
            LIBVIRT_NETWORK.DEFAULT,
            "other",
        ]
        self.patch(
            virsh.VirshSSH, "check_network_maas_dhcp_enabled"
        ).side_effect = (None, None, "br0")
        host_interfaces = [
            KnownHostInterface(
                ifname="eth0",
                attach_type=InterfaceAttachType.MACVLAN,
                dhcp_enabled=True,
            )
        ]
        ifname, attach_type = conn.get_default_interface_attachment(
            host_interfaces
        )
        # This shows us that the method returned with these values.
        self.assertEqual("eth0", ifname)
        self.assertEqual(InterfaceAttachType.MACVLAN, attach_type)

    def test_get_default_interface_attachment_errors_no_match(self):
        conn = self.configure_virshssh("")
        self.patch(virsh.VirshSSH, "get_network_list").return_value = []
        self.patch(
            virsh.VirshSSH, "check_network_maas_dhcp_enabled"
        ).side_effect = (None, None, "br0")
        host_interfaces = [
            KnownHostInterface(
                ifname=factory.make_name("error"),
                attach_type=InterfaceAttachType.MACVLAN,
                dhcp_enabled=False,
            )
        ]
        self.assertRaises(
            PodInvalidResources,
            conn.get_default_interface_attachment,
            host_interfaces,
        )

    def test_attach_interface_defaults_to_network_attachment(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        network = factory.make_name("network")
        request.known_host_interfaces = {network: True}
        domain = factory.make_name("domain")
        mock_get_default_interface_attachment = self.patch(
            virsh.VirshSSH, "get_default_interface_attachment"
        )
        mock_get_default_interface_attachment.return_value = (
            network,
            InterfaceAttachType.NETWORK,
        )
        fake_mac = factory.make_mac_address()
        interface = RequestedMachineInterface()
        self.patch(virsh, "generate_mac_address").return_value = fake_mac
        conn.attach_interface(request, interface, domain)
        conn.run.assert_called_once_with(
            [
                "attach-interface",
                domain,
                "network",
                network,
                "--mac",
                fake_mac,
                "--model",
                "virtio",
                "--config",
            ]
        )

    def test_attach_interface_calls_attaches_network(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        network = factory.make_name("network")
        request.known_host_interfaces = {network: True}
        domain = factory.make_name("domain")
        mock_get_default_interface_attachment = self.patch(
            virsh.VirshSSH, "get_default_interface_attachment"
        )
        mock_get_default_interface_attachment.return_value = (
            network,
            InterfaceAttachType.NETWORK,
        )
        fake_mac = factory.make_mac_address()
        interface = RequestedMachineInterface(
            attach_name=network, attach_type="network"
        )
        self.patch(virsh, "generate_mac_address").return_value = fake_mac
        conn.attach_interface(request, interface, domain)
        conn.run.assert_called_once_with(
            [
                "attach-interface",
                domain,
                "network",
                network,
                "--mac",
                fake_mac,
                "--model",
                "virtio",
                "--config",
            ]
        )

    def test_attach_interface_attaches_macvlan(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        domain = factory.make_name("domain")
        fake_mac = factory.make_mac_address()
        interface = RequestedMachineInterface(
            attach_name=factory.make_name("name"),
            attach_type=InterfaceAttachType.MACVLAN,
            attach_options=factory.pick_choice(MACVLAN_MODE_CHOICES),
        )
        self.patch(virsh, "generate_mac_address").return_value = fake_mac
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        conn.attach_interface(request, interface, domain)

        device_params = {
            "mac_address": fake_mac,
            "attach_name": interface.attach_name,
            "attach_options": interface.attach_options,
        }
        conn.run.assert_called_once_with(
            ["attach-device", domain, ANY, "--config"]
        )
        tmpfile.write.assert_has_calls(
            [
                call(
                    DOM_TEMPLATE_MACVLAN_INTERFACE.format(
                        **device_params
                    ).encode("utf-8")
                ),
                call(b"\n"),
            ]
        )

    def test_attach_interface_attaches_bridge(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        domain = factory.make_name("domain")
        fake_mac = factory.make_mac_address()
        interface = RequestedMachineInterface(
            attach_name=factory.make_name("ifname"),
            attach_type=InterfaceAttachType.BRIDGE,
            attach_options=factory.pick_choice(MACVLAN_MODE_CHOICES),
        )
        self.patch(virsh, "generate_mac_address").return_value = fake_mac
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        conn.attach_interface(request, interface, domain)

        device_params = {
            "mac_address": fake_mac,
            "attach_name": interface.attach_name,
        }
        conn.run.assert_called_once_with(
            ["attach-device", domain, ANY, "--config"]
        )
        tmpfile.write.assert_has_calls(
            [
                call(
                    DOM_TEMPLATE_BRIDGE_INTERFACE.format(
                        **device_params
                    ).encode("utf-8")
                ),
                call(b"\n"),
            ]
        )

    def test_get_domain_capabilities_for_kvm(self):
        conn = self.configure_virshssh(SAMPLE_CAPABILITY_KVM)
        self.assertEqual(
            {"type": "kvm", "emulator": "/usr/bin/qemu-system-x86_64"},
            conn.get_domain_capabilities(),
        )

    def test_get_domain_capabilities_for_qemu(self):
        conn = self.configure_virshssh(
            (
                virsh.VirshError("message for virsh"),
                SAMPLE_CAPABILITY_QEMU,
            )
        )
        self.assertEqual(
            {"type": "qemu", "emulator": "/usr/bin/qemu-system-x86_64"},
            conn.get_domain_capabilities(),
        )

    def test_get_domain_capabilities_raises_error(self):
        conn = self.configure_virshssh(virsh.VirshError("some error"))
        self.assertRaises(virsh.VirshError, conn.get_domain_capabilities)

    def test_cleanup_disks_deletes_all(self):
        conn = self.configure_virshssh("")
        volumes = [
            (factory.make_name("pool"), factory.make_name("vol"))
            for _ in range(3)
        ]
        mock_delete = self.patch(virsh.VirshSSH, "delete_local_volume")
        conn.cleanup_disks(volumes)
        self.assertThat(
            mock_delete,
            MockCallsMatch(*[call(pool, vol) for pool, vol in volumes]),
        )

    def test_cleanup_disks_catches_all_exceptions(self):
        conn = self.configure_virshssh("")
        volumes = [
            (factory.make_name("pool"), factory.make_name("vol"))
            for _ in range(3)
        ]
        mock_delete = self.patch(virsh.VirshSSH, "delete_local_volume")
        mock_delete.side_effect = factory.make_exception()
        # Tests that no exception is raised.
        conn.cleanup_disks(volumes)

    def test_get_block_name_from_idx(self):
        conn = self.configure_virshssh("")
        expected = [
            (0, "vda"),
            (25, "vdz"),
            (26, "vdaa"),
            (27, "vdab"),
            (51, "vdaz"),
            (52, "vdba"),
            (53, "vdbb"),
            (701, "vdzz"),
            (702, "vdaaa"),
            (703, "vdaab"),
            (18277, "vdzzz"),
        ]
        for idx, name in expected:
            self.expectThat(conn.get_block_name_from_idx(idx), Equals(name))

    def test_create_domain_fails_on_disk_create(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        exception_type = factory.make_exception_type()
        exception = factory.make_exception(bases=(exception_type,))
        first_pool, first_vol = (
            factory.make_name("pool"),
            factory.make_name("vol"),
        )
        self.patch(virsh.VirshSSH, "_create_local_volume").side_effect = [
            (first_pool, first_vol),
            exception,
        ]
        mock_cleanup = self.patch(virsh.VirshSSH, "cleanup_disks")
        error = self.assertRaises(exception_type, conn.create_domain, request)
        self.assertThat(
            mock_cleanup, MockCalledOnceWith([(first_pool, first_vol)])
        )
        self.assertIs(exception, error)

    def test_create_domain_handles_no_space(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        self.patch(virsh.VirshSSH, "_create_local_volume").return_value = None
        error = self.assertRaises(
            PodInvalidResources, conn.create_domain, request
        )
        self.assertEqual("not enough space for disk 0.", str(error))

    def test_create_domain_calls_correct_methods_with_amd64_arch(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        request.block_devices = request.block_devices[:1]
        request.interfaces = request.interfaces[:1]
        disk_info = (factory.make_name("pool"), factory.make_name("vol"))
        domain_params = {
            "type": "kvm",
            "emulator": "/usr/bin/qemu-system-x86_64",
        }
        self.patch(
            virsh.VirshSSH, "_create_local_volume"
        ).return_value = disk_info
        self.patch(
            virsh.VirshSSH, "get_domain_capabilities"
        ).return_value = domain_params
        mock_uuid = self.patch(virsh, "uuid4")
        mock_uuid.return_value = str(uuid4())
        domain_params["name"] = request.hostname
        domain_params["uuid"] = mock_uuid.return_value
        domain_params["arch"] = debian_to_kernel_architecture(
            request.architecture
        )
        domain_params["cores"] = str(request.cores)
        domain_params["memory"] = str(request.memory)
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        mock_attach_disk = self.patch(virsh.VirshSSH, "attach_local_volume")
        mock_attach_nic = self.patch(virsh.VirshSSH, "attach_interface")
        mock_check_machine_can_startup = self.patch(
            virsh.VirshSSH, "check_machine_can_startup"
        )
        mock_set_machine_autostart = self.patch(
            virsh.VirshSSH, "set_machine_autostart"
        )
        mock_configure_pxe = self.patch(virsh.VirshSSH, "configure_pxe_boot")
        mock_discovered = self.patch(virsh.VirshSSH, "get_discovered_machine")
        mock_discovered.return_value = sentinel.discovered
        observed = conn.create_domain(request)

        tmpfile.write.assert_has_calls(
            [
                call(
                    DOM_TEMPLATE_AMD64.format(**domain_params).encode("utf-8")
                ),
                call(b"\n"),
            ]
        )
        conn.run.assert_called_once_with(["define", ANY])
        self.assertThat(
            mock_attach_disk,
            MockCalledOnceWith(ANY, disk_info[0], disk_info[1], "vda"),
        )
        self.assertThat(mock_attach_nic, MockCalledOnceWith(request, ANY, ANY))
        self.assertThat(
            mock_check_machine_can_startup,
            MockCalledOnceWith(request.hostname),
        )
        self.assertThat(
            mock_set_machine_autostart, MockCalledOnceWith(request.hostname)
        )
        self.assertThat(
            mock_configure_pxe, MockCalledOnceWith(request.hostname)
        )
        self.assertThat(
            mock_discovered, MockCalledOnceWith(ANY, request=request)
        )
        self.assertEqual(sentinel.discovered, observed)

    def test_create_domain_calls_correct_methods_with_arm64_arch(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        request.architecture = "arm64/generic"
        request.block_devices = request.block_devices[:1]
        request.interfaces = request.interfaces[:1]
        disk_info = (factory.make_name("pool"), factory.make_name("vol"))
        domain_params = {
            "type": "kvm",
            "emulator": "/usr/bin/qemu-system-x86_64",
        }
        self.patch(
            virsh.VirshSSH, "_create_local_volume"
        ).return_value = disk_info
        self.patch(
            virsh.VirshSSH, "get_domain_capabilities"
        ).return_value = domain_params
        mock_uuid = self.patch(virsh, "uuid4")
        mock_uuid.return_value = str(uuid4())
        domain_params["name"] = request.hostname
        domain_params["uuid"] = mock_uuid.return_value
        domain_params["arch"] = debian_to_kernel_architecture(
            request.architecture
        )
        domain_params["cores"] = str(request.cores)
        domain_params["memory"] = str(request.memory)
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        mock_attach_disk = self.patch(virsh.VirshSSH, "attach_local_volume")
        mock_attach_nic = self.patch(virsh.VirshSSH, "attach_interface")
        mock_check_machine_can_startup = self.patch(
            virsh.VirshSSH, "check_machine_can_startup"
        )
        mock_set_machine_autostart = self.patch(
            virsh.VirshSSH, "set_machine_autostart"
        )
        mock_configure_pxe = self.patch(virsh.VirshSSH, "configure_pxe_boot")
        mock_discovered = self.patch(virsh.VirshSSH, "get_discovered_machine")
        mock_discovered.return_value = sentinel.discovered
        observed = conn.create_domain(request)

        tmpfile.write.assert_has_calls(
            [
                call(
                    DOM_TEMPLATE_ARM64.format(**domain_params).encode("utf-8")
                ),
                call(b"\n"),
            ]
        )
        conn.run.assert_called_once_with(["define", ANY])
        mock_attach_disk.assert_called_once_with(
            ANY, disk_info[0], disk_info[1], "vda"
        )
        mock_attach_nic.assert_called_once_with(request, ANY, ANY)
        mock_check_machine_can_startup.assert_called_once_with(
            request.hostname
        )
        mock_set_machine_autostart.assert_called_once_with(request.hostname)
        mock_configure_pxe.assert_called_once_with(request.hostname)
        mock_discovered.assert_called_once_with(ANY, request=request)
        self.assertEqual(sentinel.discovered, observed)

    def test_create_domain_calls_correct_methods_with_ppc64_arch(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        request.architecture = "ppc64el/generic"
        request.block_devices = request.block_devices[:1]
        request.interfaces = request.interfaces[:1]
        disk_info = (factory.make_name("pool"), factory.make_name("vol"))
        domain_params = {
            "type": "kvm",
            "emulator": "/usr/bin/qemu-system-x86_64",
        }
        self.patch(
            virsh.VirshSSH, "_create_local_volume"
        ).return_value = disk_info
        self.patch(
            virsh.VirshSSH, "get_domain_capabilities"
        ).return_value = domain_params
        mock_uuid = self.patch(virsh, "uuid4")
        mock_uuid.return_value = str(uuid4())
        domain_params["name"] = request.hostname
        domain_params["uuid"] = mock_uuid.return_value
        domain_params["arch"] = debian_to_kernel_architecture(
            request.architecture
        )
        domain_params["cores"] = str(request.cores)
        domain_params["memory"] = str(request.memory)
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        mock_attach_disk = self.patch(virsh.VirshSSH, "attach_local_volume")
        mock_attach_nic = self.patch(virsh.VirshSSH, "attach_interface")
        mock_check_machine_can_startup = self.patch(
            virsh.VirshSSH, "check_machine_can_startup"
        )
        mock_set_machine_autostart = self.patch(
            virsh.VirshSSH, "set_machine_autostart"
        )
        mock_configure_pxe = self.patch(virsh.VirshSSH, "configure_pxe_boot")
        mock_discovered = self.patch(virsh.VirshSSH, "get_discovered_machine")
        mock_discovered.return_value = sentinel.discovered
        observed = conn.create_domain(request)

        tmpfile.write.assert_has_calls(
            [
                call(
                    DOM_TEMPLATE_PPC64.format(**domain_params).encode("utf-8")
                ),
                call(b"\n"),
            ],
        )
        conn.run.assert_called_once_with(["define", ANY])
        mock_attach_disk.assert_called_once_with(
            ANY, disk_info[0], disk_info[1], "vda"
        )
        mock_attach_nic.assert_called_once_with(request, ANY, ANY)
        mock_check_machine_can_startup.assert_called_once_with(
            request.hostname
        )
        mock_set_machine_autostart.assert_called_once_with(request.hostname)
        mock_configure_pxe.assert_called_once_with(request.hostname)
        mock_discovered.assert_called_once_with(ANY, request=request)
        self.assertEqual(sentinel.discovered, observed)

    def test_create_domain_calls_correct_methods_with_s390x_arch(self):
        conn = self.configure_virshssh("")
        request = make_requested_machine()
        request.architecture = "s390x/generic"
        request.block_devices = request.block_devices[:1]
        request.interfaces = request.interfaces[:1]
        disk_info = (factory.make_name("pool"), factory.make_name("vol"))
        domain_params = {
            "type": "kvm",
            "emulator": "/usr/bin/qemu-system-x86_64",
        }
        self.patch(
            virsh.VirshSSH, "_create_local_volume"
        ).return_value = disk_info
        self.patch(
            virsh.VirshSSH, "get_domain_capabilities"
        ).return_value = domain_params
        mock_uuid = self.patch(virsh, "uuid4")
        mock_uuid.return_value = str(uuid4())
        domain_params["name"] = request.hostname
        domain_params["uuid"] = mock_uuid.return_value
        domain_params["arch"] = debian_to_kernel_architecture(
            request.architecture
        )
        domain_params["cores"] = str(request.cores)
        domain_params["memory"] = str(request.memory)
        NamedTemporaryFile = self.patch(virsh, "NamedTemporaryFile")
        tmpfile = NamedTemporaryFile.return_value
        tmpfile.__enter__.return_value = tmpfile
        tmpfile.name = factory.make_name("filename")
        mock_attach_disk = self.patch(virsh.VirshSSH, "attach_local_volume")
        mock_attach_nic = self.patch(virsh.VirshSSH, "attach_interface")
        mock_check_machine_can_startup = self.patch(
            virsh.VirshSSH, "check_machine_can_startup"
        )
        mock_set_machine_autostart = self.patch(
            virsh.VirshSSH, "set_machine_autostart"
        )
        mock_configure_pxe = self.patch(virsh.VirshSSH, "configure_pxe_boot")
        mock_discovered = self.patch(virsh.VirshSSH, "get_discovered_machine")
        mock_discovered.return_value = sentinel.discovered
        observed = conn.create_domain(request)

        tmpfile.write.assert_has_calls(
            [
                call(
                    DOM_TEMPLATE_S390X.format(**domain_params).encode("utf-8")
                ),
                call(b"\n"),
            ]
        )
        conn.run.assert_called_once_with(["define", ANY])
        mock_attach_disk.assert_called_once_with(
            ANY, disk_info[0], disk_info[1], "vda"
        )
        mock_attach_nic.assert_called_once_with(request, ANY, ANY)
        mock_check_machine_can_startup.assert_called_once_with(
            request.hostname
        )
        mock_set_machine_autostart.assert_called_once_with(request.hostname)
        mock_configure_pxe.assert_called_once_with(request.hostname)
        mock_discovered.assert_called_once_with(ANY, request=request)
        self.assertEqual(sentinel.discovered, observed)

    def test_delete_domain_calls_correct_methods(self):
        conn = self.configure_virshssh("")
        domain = factory.make_name("vm")
        conn.delete_domain(domain)
        conn.run.assert_has_calls(
            [
                call(["destroy", domain], raise_error=False),
                call(
                    [
                        "undefine",
                        domain,
                        "--remove-all-storage",
                        "--managed-save",
                        "--nvram",
                    ],
                    raise_error=False,
                ),
            ]
        )


class TestVirsh(MAASTestCase):
    """Tests for `probe_virsh_and_enlist`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

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
                self.assertEqual("network", boot_elements[0].attrib["dev"])
                self.assertEqual("hd", boot_elements[1].attrib["dev"])
        return ""

    @inlineCallbacks
    def test_probe_and_enlist(self):
        # Patch VirshSSH list so that some machines are returned
        # with some fake architectures.
        user = factory.make_name("user")
        system_id = factory.make_name("system_id")
        machines = [factory.make_name("machine") for _ in range(5)]
        self.patch(virsh.VirshSSH, "list_machines").return_value = machines
        fake_arch = factory.make_name("arch")
        mock_arch = self.patch(virsh.VirshSSH, "get_machine_arch")
        mock_arch.return_value = fake_arch
        domain = factory.make_name("domain")

        # Patch get_state so that one of the machines is on, so we
        # can check that it will be forced off.
        fake_states = [
            virsh.VirshVMState.ON,
            virsh.VirshVMState.OFF,
            virsh.VirshVMState.OFF,
            virsh.VirshVMState.ON,
            virsh.VirshVMState.ON,
        ]
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.side_effect = fake_states

        # Setup the power parameters that we should expect to be
        # the output of the probe_and_enlist
        fake_password = factory.make_string()
        poweraddr = factory.make_name("poweraddr")
        called_params = []
        fake_macs = []
        fake_ifinfo = []
        for machine in machines:
            macs = [factory.make_mac_address() for _ in range(4)]
            ifinfo = [
                InterfaceInfo("bridge", "br0", "virtio", mac) for mac in macs
            ]
            fake_ifinfo.append(ifinfo)
            fake_macs.append(macs)
            called_params.append(
                {
                    "power_address": poweraddr,
                    "power_id": machine,
                    "power_pass": fake_password,
                }
            )

        # Patch the get_mac_addresses so we get a known list of
        # mac addresses for each machine.
        mock_ifinfo = self.patch(virsh.VirshSSH, "get_machine_interface_info")
        mock_ifinfo.side_effect = fake_ifinfo

        # Patch the poweroff and create as we really don't want these
        # actions to occur, but want to also check that they are called.
        mock_poweroff = self.patch(virsh.VirshSSH, "poweroff")
        mock_create_node = self.patch(virsh, "create_node")
        mock_create_node.side_effect = asynchronous(
            lambda *args, **kwargs: None if machines[4] in args else system_id
        )
        mock_commission_node = self.patch(virsh, "commission_node")

        # Patch login and logout so that we don't really contact
        # a server at the fake poweraddr
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_logout = self.patch(virsh.VirshSSH, "logout")
        mock_get_machine_xml = self.patch(virsh.VirshSSH, "get_machine_xml")
        mock_get_machine_xml.side_effect = [
            SAMPLE_DUMPXML,
            SAMPLE_DUMPXML_2,
            SAMPLE_DUMPXML_3,
            SAMPLE_DUMPXML_4,
            SAMPLE_DUMPXML,
        ]

        mock_run = self.patch(virsh.VirshSSH, "run")
        mock_run.side_effect = self._probe_and_enlist_mock_run

        # Perform the probe and enlist
        yield deferToThread(
            virsh.probe_virsh_and_enlist,
            user,
            poweraddr,
            fake_password,
            accept_all=True,
            domain=domain,
        )

        # Check that login was called with the provided poweraddr and
        # password.
        self.expectThat(
            mock_login, MockCalledOnceWith(poweraddr, fake_password)
        )

        # Check that the create command had the correct parameters for
        # each machine.
        self.expectThat(
            mock_create_node,
            MockCallsMatch(
                call(
                    fake_macs[0],
                    fake_arch,
                    "virsh",
                    called_params[0],
                    domain,
                    hostname=machines[0],
                ),
                call(
                    fake_macs[1],
                    fake_arch,
                    "virsh",
                    called_params[1],
                    domain,
                    hostname=machines[1],
                ),
                call(
                    fake_macs[2],
                    fake_arch,
                    "virsh",
                    called_params[2],
                    domain,
                    hostname=machines[2],
                ),
                call(
                    fake_macs[3],
                    fake_arch,
                    "virsh",
                    called_params[3],
                    domain,
                    hostname=machines[3],
                ),
                call(
                    fake_macs[4],
                    fake_arch,
                    "virsh",
                    called_params[4],
                    domain,
                    hostname=machines[4],
                ),
            ),
        )

        # The first and last machine should have poweroff called on it, as it
        # was initial in the on state.
        self.expectThat(
            mock_poweroff,
            MockCallsMatch(
                call(machines[0]), call(machines[3]), call(machines[4])
            ),
        )

        self.assertThat(mock_logout, MockCalledOnceWith())
        self.expectThat(
            mock_commission_node,
            MockCallsMatch(
                call(system_id, user),
                call(system_id, user),
                call(system_id, user),
                call(system_id, user),
                call(system_id, user),
            ),
        )

    @inlineCallbacks
    def test_probe_and_enlist_login_failure(self):
        user = factory.make_name("user")
        poweraddr = factory.make_name("poweraddr")
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield deferToThread(
                virsh.probe_virsh_and_enlist,
                user,
                poweraddr,
                password=factory.make_string(),
                domain=factory.make_string(),
            )


class TestVirshPodDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = virsh.VirshPodDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["libvirt-clients"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = virsh.VirshPodDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def make_context(self):
        return {
            "system_id": factory.make_name("system_id"),
            "power_address": factory.make_name("power_address"),
            "power_id": factory.make_name("power_id"),
            "power_pass": factory.make_name("power_pass"),
        }

    def test_power_on_calls_power_control_virsh(self):
        power_change = "on"
        context = self.make_context()
        driver = VirshPodDriver()
        power_control_virsh = self.patch(driver, "power_control_virsh")
        driver.power_on(context.get("system_id"), context)

        self.assertThat(
            power_control_virsh,
            MockCalledOnceWith(power_change=power_change, **context),
        )

    def test_power_off_calls_power_control_virsh(self):
        power_change = "off"
        context = self.make_context()
        driver = VirshPodDriver()
        power_control_virsh = self.patch(driver, "power_control_virsh")
        driver.power_off(context.get("system_id"), context)

        self.assertThat(
            power_control_virsh,
            MockCalledOnceWith(power_change=power_change, **context),
        )

    def test_power_query_calls_power_state_virsh(self):
        power_state = "off"
        context = self.make_context()
        driver = VirshPodDriver()
        power_state_virsh = self.patch(driver, "power_state_virsh")
        power_state_virsh.return_value = power_state
        expected_result = driver.power_query(context.get("system_id"), context)

        self.expectThat(power_state_virsh, MockCalledOnceWith(**context))
        self.expectThat(expected_result, Equals(power_state))

    @inlineCallbacks
    def test_power_control_login_failure(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield driver.power_control_virsh(
                factory.make_name("power_address"),
                factory.make_name("power_id"),
                factory.make_name("power_change"),
                power_pass=factory.make_string(),
            )

    @inlineCallbacks
    def test_power_control_on(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.OFF
        mock_poweron = self.patch(virsh.VirshSSH, "poweron")

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        yield driver.power_control_virsh(power_address, power_id, "on")

        self.assertThat(mock_login, MockCalledOnceWith(power_address, None))
        self.assertThat(mock_state, MockCalledOnceWith(power_id))
        self.assertThat(mock_poweron, MockCalledOnceWith(power_id))

    @inlineCallbacks
    def test_power_control_off(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, "poweroff")

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        yield driver.power_control_virsh(power_address, power_id, "off")

        self.assertThat(mock_login, MockCalledOnceWith(power_address, None))
        self.assertThat(mock_state, MockCalledOnceWith(power_id))
        self.assertThat(mock_poweroff, MockCalledOnceWith(power_id))

    @inlineCallbacks
    def test_power_control_bad_domain(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = None

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with ExpectedException(virsh.VirshError):
            yield driver.power_control_virsh(power_address, power_id, "on")

    @inlineCallbacks
    def test_power_control_power_failure(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, "poweroff")
        mock_poweroff.return_value = False

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with ExpectedException(virsh.VirshError):
            yield driver.power_control_virsh(power_address, power_id, "off")

    @inlineCallbacks
    def test_power_state_login_failure(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield driver.power_state_virsh(
                factory.make_name("power_address"),
                factory.make_name("power_id"),
                power_pass=factory.make_string(),
            )

    @inlineCallbacks
    def test_power_state_get_on(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.ON

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        state = yield driver.power_state_virsh(power_address, power_id)
        self.assertEqual("on", state)

    @inlineCallbacks
    def test_power_state_get_off(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = virsh.VirshVMState.OFF

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        state = yield driver.power_state_virsh(power_address, power_id)
        self.assertEqual("off", state)

    @inlineCallbacks
    def test_power_state_bad_domain(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = None

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with ExpectedException(virsh.VirshError):
            yield driver.power_state_virsh(power_address, power_id)

    @inlineCallbacks
    def test_power_state_error_on_unknown_state(self):
        driver = VirshPodDriver()
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, "get_machine_state")
        mock_state.return_value = "unknown"

        power_address = factory.make_name("power_address")
        power_id = factory.make_name("power_id")
        with ExpectedException(virsh.VirshError):
            yield driver.power_state_virsh(power_address, power_id)

    @inlineCallbacks
    def test_discover_errors_on_failed_login(self):
        driver = VirshPodDriver()
        pod_id = factory.make_name("pod_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_pass": factory.make_name("power_pass"),
        }
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = False
        with ExpectedException(virsh.VirshError):
            yield driver.discover(pod_id, context)

    @inlineCallbacks
    def test_discover(self):
        driver = VirshPodDriver()
        pod_id = factory.make_name("pod_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_pass": factory.make_name("power_pass"),
        }
        machines = [factory.make_name("machine") for _ in range(3)]
        mock_pod = MagicMock()
        mock_pod.storage_pools = sentinel.storage_pools
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_list_pools = self.patch(virsh.VirshSSH, "list_pools")
        mock_list_pools.side_effect = ([], ["default"], ["default"])
        mock_create_storage_pool = self.patch(
            virsh.VirshSSH, "create_storage_pool"
        )
        mock_get_pod_resources = self.patch(
            virsh.VirshSSH, "get_pod_resources"
        )
        mock_get_pod_resources.return_value = mock_pod
        mock_get_pod_hints = self.patch(virsh.VirshSSH, "get_pod_hints")
        mock_list_machines = self.patch(virsh.VirshSSH, "list_machines")
        mock_get_discovered_machine = self.patch(
            virsh.VirshSSH, "get_discovered_machine"
        )
        mock_list_machines.return_value = machines

        discovered_pod = yield driver.discover(pod_id, context)
        self.expectThat(mock_create_storage_pool, MockCalledOnceWith())
        self.expectThat(mock_get_pod_resources, MockCalledOnceWith())
        self.expectThat(mock_get_pod_hints, MockCalledOnceWith())
        self.expectThat(mock_list_machines, MockCalledOnceWith())
        self.expectThat(
            mock_get_discovered_machine,
            MockCallsMatch(
                call(machines[0], storage_pools=sentinel.storage_pools),
                call(machines[1], storage_pools=sentinel.storage_pools),
                call(machines[2], storage_pools=sentinel.storage_pools),
            ),
        )
        self.expectThat(["virtual"], Equals(discovered_pod.tags))

    @inlineCallbacks
    def test_compose(self):
        driver = VirshPodDriver()
        pod_id = factory.make_name("pod_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_pass": factory.make_name("power_pass"),
        }
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        mock_create_domain = self.patch(virsh.VirshSSH, "create_domain")
        mock_create_domain.return_value = sentinel.discovered
        mock_get_pod_hints = self.patch(virsh.VirshSSH, "get_pod_hints")
        mock_get_pod_hints.return_value = sentinel.hints

        discovered, hints = yield driver.compose(
            pod_id, context, make_requested_machine()
        )
        self.assertEqual(sentinel.discovered, discovered)
        self.assertEqual(sentinel.hints, hints)

    @inlineCallbacks
    def test_decompose(self):
        driver = VirshPodDriver()
        pod_id = factory.make_name("pod_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_pass": factory.make_name("power_pass"),
            "power_id": factory.make_name("power_id"),
        }
        mock_login = self.patch(virsh.VirshSSH, "login")
        mock_login.return_value = True
        self.patch(virsh.VirshSSH, "delete_domain")
        mock_get_pod_hints = self.patch(virsh.VirshSSH, "get_pod_hints")
        mock_get_pod_hints.return_value = sentinel.hints

        hints = yield driver.decompose(pod_id, context)
        self.assertEqual(sentinel.hints, hints)
