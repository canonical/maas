# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.hardware.esxi`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    )
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
    )
from mock import call
from provisioningserver.drivers.hardware import esxi as virsh
from provisioningserver.utils.twisted import asynchronous
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


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


class TestESXi(MAASTestCase):
    """Tests for `probe_esxi_and_enlist`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_probe_and_enlist(self):
        # Patch VirshSSH list so that some machines are returned
        # with some fake architectures.
        user = factory.make_name('user')
        system_id = factory.make_name('system_id')
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
        esx_poweraddr = "esx://%s@%s/?no_verify=1" % (user, poweraddr)
        called_params = []
        fake_macs = []
        for machine in machines:
            macs = [factory.make_mac_address() for _ in range(3)]
            fake_macs.append(macs)
            called_params.append({
                'power_address': poweraddr,
                'power_id': machine,
                'power_pass': fake_password,
                'power_user': user,
                })

        # Patch the get_mac_addresses so we get a known list of
        # mac addresses for each machine.
        mock_macs = self.patch(virsh.VirshSSH, 'get_mac_addresses')
        mock_macs.side_effect = fake_macs

        # Patch the poweroff and create as we really don't want these
        # actions to occur, but want to also check that they are called.
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')
        mock_create_node = self.patch(virsh, 'create_node')
        mock_create_node.side_effect = asynchronous(lambda *args: system_id)
        mock_commission_node = self.patch(virsh, 'commission_node')

        # Patch login and logout so that we don't really contact
        # a server at the fake poweraddr
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_logout = self.patch(virsh.VirshSSH, 'logout')

        # Perform the probe and enlist
        yield deferToThread(
            virsh.probe_esxi_and_enlist,
            user, poweraddr, password=fake_password, accept_all=True)

        # Check that login was called with the provided poweraddr and
        # password.
        self.expectThat(
            mock_login, MockCalledOnceWith(esx_poweraddr, fake_password))

        # The first machine should have poweroff called on it, as it
        # was initial in the on state.
        self.expectThat(
            mock_poweroff, MockCalledOnceWith(machines[0]))

        # Check that the create command had the correct parameters for
        # each machine.
        self.expectThat(
            mock_create_node, MockCallsMatch(
                call(
                    fake_macs[0], fake_arch, 'esxi', called_params[0]),
                call(
                    fake_macs[1], fake_arch, 'esxi', called_params[1]),
                call(
                    fake_macs[2], fake_arch,
                    'esxi', called_params[2])))
        mock_logout.assert_called()
        self.expectThat(
            mock_commission_node,
            MockCalledWith(system_id, user))

    @inlineCallbacks
    def test_probe_and_enlist_login_failure(self):
        user = factory.make_name('user')
        poweraddr = factory.make_name('poweraddr')
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        with ExpectedException(virsh.ESXiError):
            yield deferToThread(
                virsh.probe_esxi_and_enlist,
                user, poweraddr, password=factory.make_string())


class TestESXiPowerControl(MAASTestCase):
    """Tests for `power_control_esxi`."""

    def test_power_control_login_failure(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        self.assertRaises(
            virsh.ESXiError, virsh.power_control_esxi,
            factory.make_name('poweraddr'), factory.make_name('machine'), 'on',
            factory.make_name('username'), password=factory.make_string())

    def test_power_control_on(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.OFF
        mock_poweron = self.patch(virsh.VirshSSH, 'poweron')

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        username = factory.make_name('user')
        password = factory.make_string()
        esx_poweraddr = "esx://%s@%s/?no_verify=1" % (username, poweraddr)
        virsh.power_control_esxi(poweraddr, machine, 'on', username, password)

        self.assertThat(
            mock_login, MockCalledOnceWith(esx_poweraddr, password))
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
        username = factory.make_name('user')
        password = factory.make_string()
        esx_poweraddr = "esx://%s@%s/?no_verify=1" % (username, poweraddr)
        virsh.power_control_esxi(poweraddr, machine, 'off', username, password)

        self.assertThat(
            mock_login, MockCalledOnceWith(esx_poweraddr, password))
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
        username = factory.make_name('user')
        password = factory.make_string()
        self.assertRaises(
            virsh.ESXiError, virsh.power_control_esxi,
            poweraddr, machine, 'on', username, password)

    def test_power_control_power_failure(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.ON
        mock_poweroff = self.patch(virsh.VirshSSH, 'poweroff')
        mock_poweroff.return_value = False

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        username = factory.make_name('user')
        password = factory.make_string()
        self.assertRaises(
            virsh.ESXiError, virsh.power_control_esxi,
            poweraddr, machine, 'off', username, password)


class TestESXiPowerState(MAASTestCase):
    """Tests for `power_state_esxi`."""

    def test_power_state_login_failure(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = False
        self.assertRaises(
            virsh.ESXiError, virsh.power_state_esxi,
            factory.make_name('poweraddr'), factory.make_name('machine'),
            factory.make_name('user'), password=factory.make_string())

    def test_power_state_get_on(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.ON

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        username = factory.make_name('user')
        password = factory.make_string()
        self.assertEqual(
            'on', virsh.power_state_esxi(poweraddr, machine,
                                         username, password))

    def test_power_state_get_off(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = virsh.VirshVMState.OFF

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        username = factory.make_name('user')
        password = factory.make_string()
        self.assertEqual(
            'off', virsh.power_state_esxi(poweraddr, machine,
                                          username, password))

    def test_power_control_bad_domain(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = None

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        username = factory.make_name('user')
        password = factory.make_string()
        self.assertRaises(
            virsh.ESXiError, virsh.power_state_esxi,
            poweraddr, machine, username, password)

    def test_power_state_error_on_unknown_state(self):
        mock_login = self.patch(virsh.VirshSSH, 'login')
        mock_login.return_value = True
        mock_state = self.patch(virsh.VirshSSH, 'get_state')
        mock_state.return_value = 'unknown'

        poweraddr = factory.make_name('poweraddr')
        machine = factory.make_name('machine')
        username = factory.make_name('user')
        password = factory.make_string()
        self.assertRaises(
            virsh.ESXiError, virsh.power_state_esxi,
            poweraddr, machine, username, password)
