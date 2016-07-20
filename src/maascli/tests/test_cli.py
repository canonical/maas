# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.cli`."""

__all__ = []

import doctest
from io import StringIO
import sys
from textwrap import dedent
from unittest.mock import sentinel

from apiclient.creds import convert_string_to_tuple
from django.core import management
from maascli import cli
from maascli.auth import UnexpectedResponse
from maascli.parser import ArgumentParser
from maascli.tests.test_auth import make_options
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from testtools.matchers import DocTestMatches


class TestRegisterCommands(MAASTestCase):
    """Tests for registers CLI commands."""

    def test_registers_subparsers(self):
        parser = ArgumentParser()
        self.assertIsNone(parser._subparsers)
        cli.register_cli_commands(parser)
        self.assertIsNotNone(parser._subparsers)

    def test_subparsers_have_appropriate_execute_defaults(self):
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        self.assertIsInstance(
            parser.subparsers.choices['login'].get_default('execute'),
            cli.cmd_login)

    def test_doesnt_call_load_regiond_commands_if_no_management(self):
        self.patch(
            cli, "get_django_management").return_value = None
        self.patch(
            cli,
            "is_maasserver_available").return_value = sentinel.pkg_util
        mock_load_regiond_commands = self.patch(cli, "load_regiond_commands")
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        self.assertThat(mock_load_regiond_commands, MockNotCalled())

    def test_doesnt_call_load_regiond_commands_if_no_maasserver(self):
        self.patch(
            cli, "get_django_management").return_value = sentinel.management
        self.patch(
            cli, "is_maasserver_available").return_value = None
        mock_load_regiond_commands = self.patch(cli, "load_regiond_commands")
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        self.assertThat(mock_load_regiond_commands, MockNotCalled())

    def test_calls_load_regiond_commands_when_management_and_maasserver(self):
        self.patch(
            cli, "get_django_management").return_value = sentinel.management
        self.patch(
            cli,
            "is_maasserver_available").return_value = sentinel.pkg_util
        mock_load_regiond_commands = self.patch(cli, "load_regiond_commands")
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        self.assertThat(
            mock_load_regiond_commands,
            MockCalledOnceWith(sentinel.management, parser))

    def test_loads_all_regiond_commands(self):
        parser = ArgumentParser()
        cli.register_cli_commands(parser)
        for name, app, help_text in cli.regiond_commands:
            subparser = parser.subparsers.choices.get(name)
            klass = management.load_command_class(app, name)
            if help_text is None:
                help_text = klass.help
            self.assertIsNotNone(subparser)
            self.assertEqual(help_text, subparser.description)


class TestLogin(MAASTestCase):

    def test_cmd_login_ensures_valid_apikey(self):
        parser = ArgumentParser()
        options = make_options()
        check_key = self.patch(cli, "check_valid_apikey")
        check_key.return_value = False
        login = cli.cmd_login(parser)
        error = self.assertRaises(SystemExit, login, options)
        self.assertEqual(
            "The MAAS server rejected your API key.",
            str(error))
        self.assertThat(check_key, MockCalledOnceWith(
            options.url, convert_string_to_tuple(options.credentials),
            options.insecure))

    def test_cmd_login_raises_unexpected_error_when_validating_apikey(self):
        parser = ArgumentParser()
        options = make_options()
        check_key = self.patch(cli, "check_valid_apikey")
        check_key_error_message = factory.make_name("error")
        check_key_error = UnexpectedResponse(check_key_error_message)
        check_key.side_effect = check_key_error
        login = cli.cmd_login(parser)
        error = self.assertRaises(SystemExit, login, options)
        self.assertEqual(check_key_error_message, str(error))

    def test_print_whats_next(self):
        profile = {
            "name": factory.make_name("profile"),
            "url": factory.make_name("url"),
            }
        stdout = self.patch(sys, "stdout", StringIO())
        cli.cmd_login.print_whats_next(profile)
        expected = dedent("""\

            You are now logged in to the MAAS server at %(url)s
            with the profile name '%(name)s'.

            For help with the available commands, try:

              maas %(name)s --help

            """) % profile
        observed = stdout.getvalue()
        flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
        self.assertThat(observed, DocTestMatches(expected, flags))
