# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.mscm``."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import randint
import re
from StringIO import StringIO

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver.drivers.hardware.mscm import MSCM_CLI_API


def make_mscm_api():
    """Make a MSCM_CLI_API object with randomized parameters."""
    host = factory.make_hostname('mscm')
    username = factory.make_name('user')
    password = factory.make_name('password')
    return MSCM_CLI_API(host, username, password)


def make_node_id():
    """Make a node_id."""
    return 'c%sn%s' % (randint(1, 45), randint(1, 8))


def make_show_node_list(length=10):
    """Make a fake return value for discover_nodes."""
    return re.findall(r'c\d+n\d', ''.join(make_node_id()
                                          for _ in xrange(length)))


def make_show_node_macaddr(length=10):
    """Make a fake return value for get_node_macaddr."""
    return ''.join((factory.getRandomMACAddress() + ' ')
                   for _ in xrange(length))


class TestRunCliCommand(MAASTestCase):
    """Tests for ``MSCM_CLI_API.run_cli_command``."""

    def test_returns_output(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api._run_cli_command(factory.make_name('command'))
        self.assertEqual(expected, output)

    def test_connects_and_closes_ssh_client(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        ssh_mock.exec_command = Mock(return_value=factory.make_streams())
        api._run_cli_command(factory.make_name('command'))
        self.assertThat(
            ssh_mock.connect,
            MockCalledOnceWith(
                api.host, username=api.username, password=api.password))
        self.assertThat(ssh_mock.close, MockCalledOnceWith())

    def test_closes_when_exception_raised(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')

        def fail():
            raise Exception('fail')

        ssh_mock.exec_command = Mock(side_effect=fail)
        command = factory.make_name('command')
        self.assertRaises(Exception, api._run_cli_command, command)
        self.assertThat(ssh_mock.close, MockCalledOnceWith())


class TestDiscoverNodes(MAASTestCase):
    """Tests for ``MSCM_CLI_API.discover_nodes``."""

    def test_discover_nodes(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        expected = make_show_node_list()
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api.discover_nodes()
        self.assertEqual(expected, output)


class TestPowerAndConfigureNode(MAASTestCase):
    """Tests for ``MSCM_CLI_API.power_node_on,
    MSCM_CLI_API.power_node_off, ``MSCM_CLI_API.configure_node_boot_pxe
    and MSCM_CLI_API.configure_node_bootonce_pxe``.
    """

    scenarios = [
        ('power_node_on()',
            dict(method='power_node_on')),
        ('power_node_off()',
            dict(method='power_node_off')),
        ('configure_node_boot_pxe()',
            dict(method='configure_node_boot_pxe')),
        ('configure_node_bootonce_pxe()',
            dict(method='configure_node_bootonce_pxe')),
    ]

    def test_returns_expected_outout(self):
        api = make_mscm_api()
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = getattr(api, self.method)(make_node_id())
        self.assertEqual(expected, output)


class TestNodeMACAddress(MAASTestCase):
    """Tests for ``MSCM_CLI_API.get_node_macaddr``."""

    def test_get_node_macaddr(self):
        api = make_mscm_api()
        expected = make_show_node_macaddr()
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        node_id = make_node_id()
        output = api.get_node_macaddr(node_id)
        self.assertEqual(re.findall(r':'.join(['[0-9a-f]{2}'] * 6),
                                    expected), output)


class TestNodeArch(MAASTestCase):
    """Tests for ``MSCM_CLI_API.get_node_arch``."""

    def test_get_node_arch(self):
        api = make_mscm_api()
        expected = '\r\n    CPU: Some Architecture\r\n'
        cli_mock = self.patch(api, '_run_cli_command')
        cli_mock.return_value = expected
        node_id = make_node_id()
        output = api.get_node_arch(node_id)
        self.assertEqual(expected.split('CPU: ')[1].splitlines()[0], output)
