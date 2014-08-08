# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.cli`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from cStringIO import StringIO
import doctest
import sys
from textwrap import dedent

from maascli import cli
from maascli.parser import ArgumentParser
from maascli.tests.test_auth import make_options
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from testtools.matchers import DocTestMatches


class TestRegisterCLICommands(MAASTestCase):
    """Tests for `register_cli_commands`."""

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


class TestLogin(MAASTestCase):

    def test_cmd_login_calls_check_valid_apikey(self):
        parser = ArgumentParser()
        options = make_options()
        check_key = self.patch(cli, "check_valid_apikey")
        check_key.return_value = False
        stdout = self.patch(sys, "stdout", StringIO())
        expected = "MAAS server rejected your API key.\n"
        login = cli.cmd_login(parser)
        login(options)
        observed = stdout.getvalue()
        self.assertThat(check_key, MockCalledOnceWith(options))
        self.assertEqual(expected, observed)

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
