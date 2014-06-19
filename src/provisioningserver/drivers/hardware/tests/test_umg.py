# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.drivers.hardware.umg``."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from random import (
    randint,
    shuffle,
    )
from StringIO import StringIO

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import Mock
from provisioningserver.drivers.hardware.umg import (
    ShowOutput,
    UMG_CLI_API,
    )


def make_umg_api():
    """Make a UMG_CLI_API object with randomized parameters."""
    host = factory.make_hostname('umg')
    username = factory.make_name('user')
    password = factory.make_name('password')
    return UMG_CLI_API(host, username, password)


class TestRunCliCommand(MAASTestCase):
    """Tests for ``UMG_CLI_API.run_cli_command``.
    """

    def test_uses_full_cli_command(self):
        api = make_umg_api()
        ssh_mock = self.patch(api, '_ssh')
        ssh_mock.exec_command = Mock(return_value=factory.make_streams())
        command = factory.make_name('command')
        api._run_cli_command(command)
        full_command = 'cli -s %s' % command
        self.assertThat(
            ssh_mock.exec_command, MockCalledOnceWith(full_command))

    def test_returns_output(self):
        api = make_umg_api()
        ssh_mock = self.patch(api, '_ssh')
        expected = factory.make_name('output')
        stdout = StringIO(expected)
        streams = factory.make_streams(stdout=stdout)
        ssh_mock.exec_command = Mock(return_value=streams)
        output = api._run_cli_command(factory.make_name('command'))
        self.assertEqual(expected, output)

    def test_connects_and_closes_ssh_client(self):
        api = make_umg_api()
        ssh_mock = self.patch(api, '_ssh')
        ssh_mock.exec_command = Mock(return_value=factory.make_streams())
        api._run_cli_command(factory.make_name('command'))
        self.assertThat(
            ssh_mock.connect,
            MockCalledOnceWith(
                api.host, username=api.username, password=api.password))
        self.assertThat(ssh_mock.close, MockCalledOnceWith())

    def test_closes_when_exception_raised(self):
        api = make_umg_api()
        ssh_mock = self.patch(api, '_ssh')

        def fail():
            raise Exception('fail')

        ssh_mock.exec_command = Mock(side_effect=fail)
        command = factory.make_name('command')
        self.assertRaises(Exception, api._run_cli_command, command)
        self.assertThat(ssh_mock.close, MockCalledOnceWith())


def make_directories(count):
    """Make a fake CLI directory listing.

    Returns a tuple of the list of the directories, and the raw text of
    the directories (to be parsed).
    """
    names = list(factory.make_names(*(['directory'] * count)))
    directories = ['|__%s\r\n' % name for name in names]
    return names, ''.join(directories)


def make_settings(count):
    """Make a fake CLI settings listing.

    Returns a tuple of the list of the settings, and the raw text of the
    settings (to be parsed).
    """
    keys = ['key%d' % i for i in range(count)]
    records = {key: factory.make_name('value') for key in keys}
    settings = [' * %s=%s\r\n' % (k, v) for k, v in records.iteritems()]
    return records, ''.join(settings)


class TestParseShowOutput(MAASTestCase):
    """Tests for ``UMG_CLI_API._parse_show_output``."""

    def test_only_directories(self):
        api = make_umg_api()
        directories, parser_input = make_directories(randint(1, 10))
        results = api._parse_show_output(parser_input)
        self.assertEqual(directories, results.directories)

    def test_only_settings(self):
        api = make_umg_api()
        settings, parser_input = make_settings(randint(1, 10))
        results = api._parse_show_output(parser_input)
        self.assertEqual(settings, results.settings)

    def test_empty_input(self):
        api = make_umg_api()
        results = api._parse_show_output('')
        self.assertEqual(ShowOutput([], {}), results)

    def test_directories_and_settings_in_mixed_order(self):
        api = make_umg_api()
        directories, directories_input = make_directories(randint(1, 10))
        settings, settings_input = make_settings(randint(1, 10))
        combined = directories_input + settings_input
        lines = combined.split('\r\n')
        shuffle(lines)
        shuffled = '\r\n'.join(lines) + '\r\n'
        results = api._parse_show_output(shuffled)
        self.assertItemsEqual(directories, results.directories)
        self.assertEqual(settings, results.settings)


class TestShowCommand(MAASTestCase):
    """Tests for ``UMG_CLI_API._show_command``."""

    def test_runs_command_and_returns_parsed_results(self):
        api = make_umg_api()
        command = factory.make_name('command')
        run_cli_command = self.patch(api, '_run_cli_command')
        run_cli_command.return_value = factory.make_name('output_text')
        parse_show_output = self.patch(api, '_parse_show_output')
        parse_show_output.return_value = factory.make_name('parsed_result')
        result = api._show_command(command)
        self.assertThat(run_cli_command, MockCalledOnceWith(command))
        expected_call = MockCalledOnceWith(run_cli_command.return_value)
        self.assertThat(parse_show_output, expected_call)
        self.assertEqual(parse_show_output.return_value, result)


class TestShowTargets(MAASTestCase):
    """Tests for ``UMG_CLI_API.show_targets``."""

    def test_uses_correct_command(self):
        api = make_umg_api()
        show_command = self.patch(api, '_show_command')
        api.show_targets()
        self.assertThat(show_command, MockCalledOnceWith('show /targets/SP'))

    def test_returns_command_output(self):
        api = make_umg_api()
        show_command = self.patch(api, '_show_command')
        show_command.return_value = factory.make_name('result')
        result = api.show_targets()
        self.assertEqual(show_command.return_value, result)


class TestShowTarget(MAASTestCase):
    """Tests for ``UMG_CLI_API.show_target``."""

    def test_uses_correct_command(self):
        api = make_umg_api()
        show_command = self.patch(api, '_show_command')
        target = factory.make_name('target')
        api.show_target(target)
        expected = 'show /targets/SP/%s' % (target)
        self.assertThat(show_command, MockCalledOnceWith(expected))

    def test_returns_command_output(self):
        api = make_umg_api()
        show_command = self.patch(api, '_show_command')
        show_command.return_value = factory.make_name('result')
        result = api.show_target(factory.make_name('target'))
        self.assertEqual(show_command.return_value, result)


class TestPowerControlTarget(MAASTestCase):
    """"Tests for ``UMG_CLI_API.power_control_target``."""

    def test_uses_correct_command(self):
        api = make_umg_api()
        target = factory.make_name('target')
        power_control = factory.make_name('power_control')
        run_cli_command = self.patch(api, '_run_cli_command')
        api.power_control_target(target, power_control)
        expected = 'set targets/SP/%s/powerControl powerCtrlType=%s' % (
            target, power_control)
        self.assertThat(run_cli_command, MockCalledOnceWith(expected))
