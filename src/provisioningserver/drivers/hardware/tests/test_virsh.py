# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.hardware.virsh`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
from mock import call
from provisioningserver.drivers.hardware import virsh
import provisioningserver.utils as utils


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
        <boot dev='network'/>
      </os>
    </domain>
    """)


class TestVirshSSH(MAASTestCase):
    """Tests for `VirshSSH`."""

    def configure_virshssh_pexpect(self, inputs=None):
        """Configures the VirshSSH class to use 'cat' process
        for testing instead of the actual virsh."""
        conn = virsh.VirshSSH(timeout=0.1)
        self.addCleanup(conn.close)
        self.patch(conn, '_execute')
        conn._spawn('cat')
        if inputs is not None:
            for line in inputs:
                conn.sendline(line)
        return conn

    def configure_virshssh(self, output):
        self.patch(virsh.VirshSSH, 'run').return_value = output
        return virsh.VirshSSH()

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
            "ubuntu@%s's password: " % factory.getRandomIPAddress(),
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        fake_password = factory.make_name('password')
        mock_sendline = self.patch(conn, 'sendline')
        conn.login(poweraddr=None, password=fake_password)
        self.assertThat(mock_sendline, MockCalledOnceWith(fake_password))

    def test_login_missing_password(self):
        virsh_outputs = [
            "ubuntu@%s's password: " % factory.getRandomIPAddress(),
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, 'close')
        self.assertFalse(conn.login(poweraddr=None, password=None))
        mock_close.assert_called()

    def test_login_invalid(self):
        virsh_outputs = [
            factory.make_string(),
        ]
        conn = self.configure_virshssh_pexpect(virsh_outputs)
        mock_close = self.patch(conn, 'close')
        self.assertFalse(conn.login(poweraddr=None))
        mock_close.assert_called()

    def test_logout(self):
        conn = self.configure_virshssh_pexpect()
        mock_sendline = self.patch(conn, 'sendline')
        mock_close = self.patch(conn, 'close')
        conn.logout()
        self.assertThat(mock_sendline, MockCalledOnceWith('quit'))
        mock_close.assert_called()

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
        conn.before = '\n'.join([expected] + names)
        mock_sendline = self.patch(conn, 'sendline')
        mock_prompt = self.patch(conn, 'prompt')
        output = conn.run(cmd)
        self.assertThat(mock_sendline, MockCalledOnceWith(expected))
        mock_prompt.assert_called()
        self.assertEqual('\n'.join(names), output)

    def test_list(self):
        names = [factory.make_name('machine') for _ in range(3)]
        conn = self.configure_virshssh('\n'.join(names))
        expected = conn.list()
        self.assertItemsEqual(names, expected)

    def test_get_state(self):
        state = factory.make_name('state')
        conn = self.configure_virshssh(state)
        expected = conn.get_state('')
        self.assertEqual(state, expected)

    def test_get_state_error(self):
        conn = self.configure_virshssh('error')
        expected = conn.get_state('')
        self.assertEqual(None, expected)

    def test_mac_addresses_returns_list(self):
        macs = [factory.getRandomMACAddress() for _ in range(2)]
        output = SAMPLE_IFLIST % (macs[0], macs[1])
        conn = self.configure_virshssh(output)
        expected = conn.get_mac_addresses('')
        for i in range(2):
            self.assertEqual(macs[i], expected[i])

    def test_get_arch_returns_valid(self):
        arch = factory.make_name('arch')
        output = SAMPLE_DUMPXML % arch
        conn = self.configure_virshssh(output)
        expected = conn.get_arch('')
        self.assertEqual(arch, expected)

    def test_get_arch_returns_valid_fixed(self):
        arch = random.choice(virsh.ARCH_FIX.keys())
        fixed_arch = virsh.ARCH_FIX[arch]
        output = SAMPLE_DUMPXML % arch
        conn = self.configure_virshssh(output)
        expected = conn.get_arch('')
        self.assertEqual(fixed_arch, expected)


class TestVirsh(MAASTestCase):
    """Tests for `probe_virsh_and_enlist`."""

    def test_probe_and_enlist(self):
        # Patch VirshSSH list so that some machines are returned
        # with some fake architectures.
        machines = [factory.make_name('machine') for _ in range(3)]
        self.patch(virsh.VirshSSH, 'list').return_value = machines
        fake_arch = factory.make_name('arch')
        mock_arch = self.patch(virsh.VirshSSH, 'get_arch')
        mock_arch.return_value = fake_arch

        # Patch get_state so that one of the machines is on, so we
        # can check that it will be forced off.
        fake_states = [
            virsh.VirshVMState.ON,
            virsh.VirshVMState.OFF,
            virsh.VirshVMState.OFF
            ]
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.side_effect = fake_states

        # Setup the power parameters that we should expect to be
        # the output of the probe_and_enlist
        fake_password = factory.make_string()
        poweraddr = factory.make_name('poweraddr')
        called_params = []
        fake_macs = []
        for machine in machines:
            macs = [factory.getRandomMACAddress() for _ in range(3)]
            fake_macs.append(macs)
            called_params.append({
                'power_address': poweraddr,
                'power_id': machine,
                'power_pass': fake_password,
                })

        # Patch the get_mac_addresses so we get a known list of
        # mac addresses for each machine.
        mock_macs = self.patch(virsh.VirshSSH, 'get_mac_addresses')
        mock_macs.side_effect = fake_macs

        # Patch the poweroff and create as we really don't want these
        # actions to occur, but want to also check that they are called.
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')
        mock_create = self.patch(utils, 'create_node')

        # Patch login and logout so that we don't really contact
        # a server at the fake poweraddr
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_logout = self.patch(virsh.VirshSSH, 'logout')

        # Perform the probe and enlist
        virsh.probe_virsh_and_enlist(poweraddr, password=fake_password)

        # Check that login was called with the provided poweraddr and
        # password.
        self.assertThat(
            mock_login, MockCalledOnceWith(poweraddr, fake_password))

        # The first machine should have poweroff called on it, as it
        # was initial in the on state.
        self.assertThat(
            mock_poweroff, MockCalledOnceWith(machines[0]))

        # Check that the create command had the correct parameters for
        # each machine.
        self.assertThat(
            mock_create, MockCallsMatch(
                call(fake_macs[0], fake_arch, 'virsh', called_params[0]),
                call(fake_macs[1], fake_arch, 'virsh', called_params[1]),
                call(fake_macs[2], fake_arch, 'virsh', called_params[2])))
        mock_logout.assert_called()

    def test_probe_and_enlist_login_failure(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        self.assertRaises(
            virsh.VirshError, virsh.probe_virsh_and_enlist,
            factory.make_name('poweraddr'), password=factory.make_string())


class TestVirshPowerControl(MAASTestCase):
    """Tests for `power_control_virsh`."""

    def test_power_control_login_failure(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        self.assertRaises(
            virsh.VirshError, virsh.power_control_virsh,
            factory.make_name('poweraddr'), factory.make_name('machine'),
            'on', password=factory.make_string())

    def test_power_control_on(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.OFF
        mock_poweron = self.patch(virsh.VirshSSH, 'poweron')

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        virsh.power_control_virsh(poweraddr, machine, 'on')

        self.assertThat(
            mock_login, MockCalledOnceWith(poweraddr, None))
        self.assertThat(
            mock_state, MockCalledOnceWith(machine))
        self.assertThat(
            mock_poweron, MockCalledOnceWith(machine))

    def test_power_control_off(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        virsh.power_control_virsh(poweraddr, machine, 'off')

        self.assertThat(
            mock_login, MockCalledOnceWith(poweraddr, None))
        self.assertThat(
            mock_state, MockCalledOnceWith(machine))
        self.assertThat(
            mock_poweroff, MockCalledOnceWith(machine))

    def test_power_control_bad_domain(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = None

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        self.assertRaises(
            virsh.VirshError, virsh.power_control_virsh,
            poweraddr, machine, 'on')

    def test_power_control_power_failure(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')
        mock_poweroff.return_value = False

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        self.assertRaises(
            virsh.VirshError, virsh.power_control_virsh,
            poweraddr, machine, 'off')
