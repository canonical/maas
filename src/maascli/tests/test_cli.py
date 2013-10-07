# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
from maastesting.factory import factory
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

              maas-cli %(name)s --help

            """) % profile
        observed = stdout.getvalue()
        flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
        self.assertThat(observed, DocTestMatches(expected, flags))
