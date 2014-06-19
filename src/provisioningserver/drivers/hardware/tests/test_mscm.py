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
