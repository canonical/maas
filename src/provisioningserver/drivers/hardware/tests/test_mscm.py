# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.mscm``."""

__all__ = []

from io import StringIO
from random import randint
import re

from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockCalledWith,
)
from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from mock import Mock
from provisioningserver.drivers.hardware import mscm
from provisioningserver.drivers.hardware.mscm import (
    cartridge_mapping,
    MSCM,
    MSCMError,
    MSCMState,
    power_control_mscm,
    power_state_mscm,
    probe_and_enlist_mscm,
)
from provisioningserver.utils.twisted import asynchronous
from testtools.matchers import Equals
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


def make_mscm_api():
    """Make a MSCM object with randomized parameters."""
    host = factory.make_hostname('mscm')
    username = factory.make_name('user')
    password = factory.make_name('password')
    return MSCM(host, username, password)


def make_node_id():
    """Make a node_id."""
    return 'c%sn%s' % (randint(1, 45), randint(1, 8))


def make_show_node_list(length=10):
    """Make a fake return value for discover_nodes."""
    return re.findall(r'c\d+n\d', ''.join(make_node_id()
                                          for _ in range(length)))


def make_show_node_macaddr(length=10):
    """Make a fake return value for get_node_macaddr."""
    return ''.join((factory.make_mac_address() + ' ')
                   for _ in range(length))


class TestMSCMCliApi(MAASTestCase):
    """Tests for `MSCM`."""

    scenarios = [
        ('power_node_on',
            dict(method='power_node_on')),
        ('power_node_off',
            dict(method='power_node_off')),
        ('configure_node_bootonce_pxe',
            dict(method='configure_node_bootonce_pxe')),
        ('configure_node_boot_m2',
            dict(method='configure_node_boot_m2')),
    ]

    def test_run_cli_command_returns_output(self):
        api = make_mscm_api()
        command = factory.make_name('command')
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api._run_cli_command(command)

        self.expectThat(expected, Equals(output))
        self.expectThat(ssh_mock.exec_command, MockCalledOnceWith(command))

    def test_run_cli_command_connects_and_closes_ssh_client(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        ssh_mock.exec_command = Mock(return_value=factory.make_streams())
        api._run_cli_command(factory.make_name('command'))

        self.expectThat(
            ssh_mock.connect,
            MockCalledOnceWith(
                api.host, username=api.username, password=api.password))
        self.expectThat(ssh_mock.close, MockCalledOnceWith())

    def test_run_cli_command_closes_when_exception_raised(self):
        api = make_mscm_api()
        exception_type = factory.make_exception_type()
        ssh_mock = self.patch(api, '_ssh')
        ssh_mock.exec_command = Mock(side_effect=exception_type)
        command = factory.make_name('command')

        self.assertRaises(exception_type, api._run_cli_command, command)
        self.expectThat(ssh_mock.close, MockCalledOnceWith())

    def test_discover_nodes(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        expected = make_show_node_list()
        stdout = StringIO("\n".join(expected))
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api.discover_nodes()
        command = "show node list"

        self.expectThat(expected, Equals(output))
        self.expectThat(ssh_mock.exec_command, MockCalledOnceWith(command))

    def test_get_node_macaddr(self):
        api = make_mscm_api()
        expected = make_show_node_macaddr()
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        node_id = make_node_id()
        output = api.get_node_macaddr(node_id)
        command = "show node macaddr %s" % node_id

        self.expectThat(re.findall(r':'.join(['[0-9a-f]{2}'] * 6),
                                   expected), Equals(output))
        self.expectThat(cli_mock, MockCalledOnceWith(command))

    def test_get_node_arch_returns_cartridge_mapping(self):
        api = make_mscm_api()
        expected = '\r\n    Product Name: ProLiant Moonshot Cartridge\r\n'
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        node_id = make_node_id()
        output = api.get_node_arch(node_id)
        command = "show node info %s" % node_id
        key = expected.split('Product Name: ')[1].splitlines()[0]

        self.expectThat(cartridge_mapping[key], Equals(output))
        self.expectThat(cli_mock, MockCalledOnceWith(command))

    def test_get_node_arch_returns_default_cartridge_mapping(self):
        api = make_mscm_api()
        expected = '\r\n    Product Name: Testing\r\n'
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        node_id = make_node_id()
        output = api.get_node_arch(node_id)
        command = "show node info %s" % node_id
        key = 'Default'

        self.expectThat(cartridge_mapping[key], Equals(output))
        self.expectThat(cli_mock, MockCalledOnceWith(command))

    def test_get_node_power_state(self):
        api = make_mscm_api()
        expected = '\r\n  Node #1\r\n    Power State: On\r\n'
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        node_id = make_node_id()
        output = api.get_node_power_state(node_id)
        command = "show node power %s" % node_id

        self.expectThat(expected.split('Power State: ')[1].splitlines()[0],
                        Equals(output))
        self.expectThat(cli_mock, MockCalledOnceWith(command))

    def test_power_and_configure_node_returns_expected_outout(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = getattr(api, self.method)(make_node_id())

        self.assertThat(expected, Equals(output))


class TestMSCMProbeAndEnlist(MAASTestCase):
    """Tests for `probe_and_enlist_mscm`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_probe_and_enlist(self):
        user = factory.make_name('user')
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        system_id = factory.make_name('system_id')
        node_id = make_node_id()
        macs = make_show_node_macaddr(4)
        arch = 'arm64/xgene-uboot'
        discover_nodes_mock = self.patch(MSCM, 'discover_nodes')
        discover_nodes_mock.return_value = [node_id]
        boot_m2_mock = self.patch(MSCM, 'configure_node_boot_m2')
        node_arch_mock = self.patch(MSCM, 'get_node_arch')
        node_arch_mock.return_value = arch
        node_macs_mock = self.patch(MSCM, 'get_node_macaddr')
        node_macs_mock.return_value = macs
        create_node_mock = self.patch(mscm, 'create_node')
        create_node_mock.side_effect = asynchronous(lambda *args: system_id)
        commission_node_mock = self.patch(mscm, 'commission_node')
        params = {
            'power_address': host,
            'power_user': username,
            'power_pass': password,
            'node_id': node_id,
        }

        yield deferToThread(
            probe_and_enlist_mscm,
            user, host, username, password, accept_all=True)

        self.expectThat(discover_nodes_mock, MockAnyCall())
        self.expectThat(boot_m2_mock, MockCalledWith(node_id))
        self.expectThat(node_arch_mock, MockCalledOnceWith(node_id))
        self.expectThat(node_macs_mock, MockCalledOnceWith(node_id))
        self.expectThat(
            create_node_mock,
            MockCalledOnceWith(macs, arch, 'mscm', params))
        self.expectThat(
            commission_node_mock,
            MockCalledOnceWith(system_id, user))

    @inlineCallbacks
    def test_probe_and_enlist_discover_nodes_failure(self):
        user = factory.make_name('user')
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        discover_nodes_mock = self.patch(MSCM, 'discover_nodes')
        discover_nodes_mock.side_effect = MSCMError('error')

        with ExpectedException(MSCMError):
            yield deferToThread(
                probe_and_enlist_mscm, user, host, username, password)


class TestMSCMPowerControl(MAASTestCase):
    """Tests for `power_control_mscm`."""

    def test_power_control_error_on_unknown_power_change(self):
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_change = factory.make_name('error')

        self.assertRaises(
            MSCMError, power_control_mscm, host,
            username, password, node_id, power_change)

    def test_power_control_power_change_on_power_state_on(self):
        # power_change and current power_state are both 'on'
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_state_mock = self.patch(MSCM, 'get_node_power_state')
        power_state_mock.return_value = MSCMState.ON
        power_node_off_mock = self.patch(MSCM, 'power_node_off')
        bootonce_mock = self.patch(MSCM, 'configure_node_bootonce_pxe')
        power_node_on_mock = self.patch(MSCM, 'power_node_on')
        power_control_mscm(host, username, password, node_id,
                           power_change='on')

        self.expectThat(power_state_mock, MockCalledOnceWith(node_id))
        self.expectThat(power_node_off_mock, MockCalledOnceWith(node_id))
        self.expectThat(bootonce_mock, MockCalledOnceWith(node_id))
        self.expectThat(power_node_on_mock, MockCalledOnceWith(node_id))

    def test_power_control_power_change_on_power_state_off(self):
        # power_change is 'on' and current power_state is 'off'
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_state_mock = self.patch(MSCM, 'get_node_power_state')
        power_state_mock.return_value = MSCMState.OFF
        bootonce_mock = self.patch(MSCM, 'configure_node_bootonce_pxe')
        power_node_on_mock = self.patch(MSCM, 'power_node_on')
        power_control_mscm(host, username, password, node_id,
                           power_change='on')

        self.expectThat(power_state_mock, MockCalledOnceWith(node_id))
        self.expectThat(bootonce_mock, MockCalledOnceWith(node_id))
        self.expectThat(power_node_on_mock, MockCalledOnceWith(node_id))

    def test_power_control_power_change_off_power_state_on(self):
        # power_change is 'off' and current power_state is 'on'
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_node_off_mock = self.patch(MSCM, 'power_node_off')
        power_control_mscm(host, username, password, node_id,
                           power_change='off')

        self.assertThat(power_node_off_mock, MockCalledOnceWith(node_id))


class TestMSCMPowerState(MAASTestCase):
    """Tests for `power_state_mscm`."""

    def test_power_state_failed_to_get_state(self):
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_state_mock = self.patch(MSCM, 'get_node_power_state')
        power_state_mock.side_effect = MSCMError('error')

        self.assertRaises(
            MSCMError, power_state_mscm, host, username, password, node_id)
        self.expectThat(power_state_mock, MockCalledOnceWith(node_id))

    def test_power_state_get_off(self):
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_state_mock = self.patch(MSCM, 'get_node_power_state')
        power_state_mock.return_value = MSCMState.OFF

        self.expectThat(
            power_state_mscm(host, username, password, node_id),
            Equals('off'))
        self.expectThat(power_state_mock, MockCalledOnceWith(node_id))

    def test_power_state_get_on(self):
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_state_mock = self.patch(MSCM, 'get_node_power_state')
        power_state_mock.return_value = MSCMState.ON

        self.expectThat(
            power_state_mscm(host, username, password, node_id),
            Equals('on'))
        self.expectThat(power_state_mock, MockCalledOnceWith(node_id))

    def test_power_state_error_on_unknown_state(self):
        host = factory.make_hostname('mscm')
        username = factory.make_name('user')
        password = factory.make_name('password')
        node_id = make_node_id()
        power_state_mock = self.patch(MSCM, 'get_node_power_state')
        power_state_mock.return_value = factory.make_name('error')

        self.assertRaises(
            MSCMError, power_state_mscm, host, username, password, node_id)
        self.expectThat(power_state_mock, MockCalledOnceWith(node_id))
